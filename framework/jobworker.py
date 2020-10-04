#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Surveyor Job Worker Process

    A work package from the input queue is a set of work items. These
    consits of a file name and set of config entries for that file.

    For each workitem, the worker designates the given file as the
    "currentFile". It then goes through all the config entries for
    the file (files are processed more than once if they are tagged
    with different measures by a config file) and delegates the measurement
    call to the appropriate module (the file is opened once and cached).

    The output from each measure call is placed in a list associated with
    that file. When the file processing is done this list is cached as
    part of "currentOutput". Once all workItems in a workPackage are
    processed, the currentOutput is posted and we start over again.
'''

import os
import sys
import time
import traceback
from multiprocessing import Process
from errno import EACCES
from queue import Empty, Full

from code_surveyor.framework import log  # No relative path to share module globals
from . import fileext
from . import uistrings
from . import utils


WORKER_PROC_BASENAME = "Job"
INPUT_EMPTY_WAIT = 0.1
CONTROL_QUEUE_TIMEOUT = 0.2
OUT_PUT_TIMEOUT = 0.4


class Worker( Process ):
    '''
    The worker class executes as separate processes spawned by the Job
    They take items from the input queue, delegate calls to the measurement
    modules, and package measures for the output queue.
    '''
    def __init__(self, inputQueue, outputQueue, controlQueue,
                    context, num, jobName=WORKER_PROC_BASENAME):
        '''
        Init is called in the parent process
        '''
        Process.__init__(self, name=jobName + str(num))
        self._inputQueue = inputQueue
        self._outputQueue = outputQueue
        self._controlQueue = controlQueue
        self._continueProcessing = True
        self._currentOutput = []
        self._currentFilePath = None
        self._currentFileIterator = None
        self._currentFileOutput = []
        self._currentFileErrors = []
        self._dbgContext, self._profileName = context
        log.cc(2, "Initialized new process: {}".format(self.name))

    def run(self):
        '''
        Process entry point - set up debug/profile context
        '''
        try:
            log.set_context(self._dbgContext)

            if self._profileName is not None:
                import cProfile;
                cProfile.runctx('self._run()', globals(), {'self': self}, 
                                    self._profileName + self.name)
            else:
                self._run()

        except Exception as e:
            # Exception is treated as fatal to worker, which will do an orderly shutdown.
            # Can't pickle tracebacks, so get in-context stack dump to send back
            log.msg(1, "EXCEPTION, stopping worker: " + str(e))
            e._stack_trace = "".join(
                traceback.format_exception(type(e), e, e.__traceback__))
            self._controlQueue.put_nowait(('JOB', 'EXCEPTION', e))
        except KeyboardInterrupt:
            log.cc(1, "Ctrl-c occurred in job worker loop")
        finally:
            log.cc(1, "TERMINATING")
            # Orderly shutdown, clean up queues  
            # Input and out queues are empty at this point (or is a hard stop),
            # so cancel_join_thread (don't wait for them to clear)
            self._inputQueue.close()
            self._inputQueue.cancel_join_thread()
            self._outputQueue.close()
            self._outputQueue.cancel_join_thread()
            # Join control queue to make sure control items are flushed
            self._controlQueue.close()
            self._controlQueue.join_thread()
            log.cc(2, "TERMINATED")

    def _run(self):
        '''
        Process items from input queue until it's empty and app signals all done
        '''
        log.cc(1, "STARTING: Begining to process input queue...")

        while self._continueProcessing:
            try:
                workPackage = self._inputQueue.get_nowait()
                log.cc(2, "GOT WorkPackage - files: {}".format(len(workPackage)))
            except Empty:
                # The input queue can return empty when it really isn't, or
                # in mid job and have burned down the empty queue
                # Sleeping after these helps performance with many cores, vs
                # just blocking on inputQueue.get
                log.cc(3, "EMPTY INPUT")
                time.sleep(INPUT_EMPTY_WAIT)
            else:
                for workItem in workPackage:
                    if not self._measure_file(workItem):
                        self._continueProcessing = False
                        break
                self._post_results()
            self._check_for_stop()

    def _check_for_stop(self):
        '''
        Command queue will normally be empty unless we are terminating.
        If there are commands, get all we can until we find our own or empty
        the queue -- then put back everything we took off. The command queue
        should never have a lot in it and this guarantees we can't deadlock.
        '''
        otherCommands = []
        myCommand = None
        try:
            while True:
                (target, command, payload) = self._controlQueue.get_nowait()
                log.cc(3, "command - {}, {}".format(target, command))
                if target == self.name:
                    myCommand = command
                    break
                else:
                    otherCommands.append((target, command, payload))
        except Empty:
            pass
        finally:
            if 'EXIT' == myCommand:
                log.cc(2, "COMMAND: EXIT")
                self._continueProcessing = False
            if otherCommands:
                log.cc(4, "replacing conmmands - {}".format(otherCommands))
                utils.put_commands(self._controlQueue, otherCommands, 
                                    CONTROL_QUEUE_TIMEOUT)

        return self._continueProcessing

    #-------------------------------------------------------------------------
    #  File measurement

    def file_measured_callback(self, filePath, measures, analysisResults):
        '''
        Callback from the masurement module
        We store up a list of tuples with the work output for a given file
        '''
        assert filePath == self._currentFilePath, "Measure callback out of sync"
        log.file(3, "_file_measured_callback: {}".format(filePath))
        log.file(3, "  measures: {}".format(measures))
        log.file(3, "  analysis: {}".format(analysisResults))
        self._currentFileOutput.append((measures, analysisResults))

    def _measure_file(self, workItem):
        '''
        Unpack workItem and run all measures requested by the configItems
        for the file
        '''
        (   path,
            deltaPath,
            fileName,
            configItems,
            options,
            numFilesInFolder
            ) = workItem

        self._currentFilePath = os.path.join(path, fileName)
        log.file(3, "Processing: {}".format(self._currentFilePath))

        deltaFilePath = None
        if deltaPath is not None:
            deltaFilePath = os.path.join(deltaPath, fileName)

        module = None
        continueProcessing = True
        try:
            for configItem in configItems:
                if not self._check_for_stop():
                    break
                module = configItem.module
                self._open_file(module, deltaFilePath)

                #
                # Synchronus delegation to the measure module defined in the config file
                #
                module.process_file(
                        self._currentFilePath,
                        self._currentFileIterator,
                        configItem,
                        numFilesInFolder,
                        self.file_measured_callback)

        except utils.FileMeasureError as e:
            log.stack(2)
            self._currentFileErrors.append(
                    uistrings.STR_ErrorMeasuringFile.format(
                            self._currentFilePath, str(e)))
            continueProcessing = not options.breakOnError
        except EnvironmentError as e:
            log.stack(2)
            if e.errno == EACCES:
                self._currentFileErrors.append(
                        uistrings.STR_ErrorOpeningMeasureFile_Access.format(
                                self._currentFilePath))
            else:
                self._currentFileErrors.append(
                        uistrings.STR_ErrorOpeningMeasureFile_Except.format(
                                self._currentFilePath, str(e)))
            continueProcessing = not options.breakOnError
        except Exception as e:
            # Treat exceptions from measuring the file as file errors 
            exc = str(type(e)) + " " + str(e)
            log.msg(1, "EXCEPTION measuring file: " + self._currentFilePath +
                        " with " + str(module) + " -> " + exc )
            log.stack(2)
            self._currentFileErrors.append(
                    uistrings.STR_ExceptionMeasureFile.format(
                            self._currentFilePath, exc))
        finally:
            self._close_current_file()
            self._file_complete()
        return continueProcessing

    def _open_file(self, module, deltaFilePath):
        '''
        Open can be expensive operation, so for the nominal case cache the
        current file iterator for use with multiple config entries.
        '''
        self._currentFileIterator = module.open_file(self._currentFilePath,
                                     deltaFilePath, self._currentFileIterator)

    def _close_current_file(self):
        '''
        Normally the fileIterator is a file handle that needs to be closed, but 
        it may just be an iterator
        '''
        if self._currentFileIterator:
            try:
                self._currentFileIterator.close()
            except AttributeError:
                pass
            self._currentFileIterator = None

    #-------------------------------------------------------------------------

    def _file_complete(self):
        '''
        Cache the output from the measurement callbacks for current file
        '''
        if self._currentFileOutput or self._currentFileErrors:
            self._currentOutput.append(
                    ( self._currentFilePath, self._currentFileOutput, 
                        self._currentFileErrors ) )
            log.file(3, "Caching results: {}".format(self._currentFilePath))
        else:
            log.file(3, "No measures for: {}".format(self._currentFilePath))
        self._currentFileOutput = []
        self._currentFileErrors = []

    def _post_results(self):
        '''
        Send any cached results back to main process's out thread
        This is a set of results for config measure of every file
        in the last work package
        '''
        try:
            self._outputQueue.put(self._currentOutput, True, OUT_PUT_TIMEOUT)
            log.cc(3, "OUT - PUT {} items".format(len(self._currentOutput)))
        except Full:
            raise utils.JobException("FATAL EXCEPTION - Out Queue full, can't put")
        finally:
            self._currentOutput = []


