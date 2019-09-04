#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    Surveyor Job Output Thread
'''

import time
import _thread
import threading
from queue import Empty, Full

from . import utils
from . import log

OUTPUT_EMPTY_WAIT = 0.02
CONTROL_QUEUE_TIMEOUT = 0.1

class OutThread( threading.Thread ):
    '''
    OutThread runs in main process, monitoring the out queue and passing
    on to Surveyor, providing seralization of results from the queue.
    '''
    def __init__(self, outQueue, controlQueue, profileName, file_measure_callback):
        log.cc(1, "Creating output queue thread")
        threading.Thread.__init__(self, name="Out")
        self._profileName = profileName

        # The main thread manages our life; if something gets truly out of
        # sync care more about exiting than ensuring output is flushed
        self.daemon = True

        # The main thread owns our queues
        self._outQueue = outQueue
        self._controlQueue = controlQueue
        self._file_measure_callback = file_measure_callback

        # Total task output packages we've received from all processes
        self.taskPackagesReceived = 0

        # Flag to track when receive WORK_DONE from the Job
        self._workDone = False

    def run(self):
        log.cc(1, "STARTING: Begining to process output queue...")
        try:
            if self._profileName is not None:
                import cProfile;
                cProfile.runctx('self._run()', globals(), {'self': self}, self._profileName + self.name)
            else:
                self._run()
            log.cc(1, "FINISHED processing output queue")

        except KeyboardInterrupt:
            log.cc(1, "Ctrl-c occurred in OUTPUT THREAD")
            _thread.interrupt_main()
        except Exception as e:
            log.msg(1, "EXCEPTION occurred processing output queue")
            self._controlQueue.put_nowait(('JOB', 'EXCEPTION', e))
            log.stack(2)
        finally:
            log.cc(1, "TERMINATING")

    def _run(self):
        # Keep processing queue until the job signals it is done and
        # the queue is empty, or receive an abort command
        while self._continue_processing():
            try:
                if self._workDone and self._outQueue.empty():
                    break
                filesOutput = self._outQueue.get_nowait()

            except Empty:
                log.cc(3, "EMPTY OUTPUT")
                time.sleep(OUTPUT_EMPTY_WAIT)
            else:
                self.taskPackagesReceived += 1
                log.cc(2, "GOT {} measures".format(len(filesOutput)))

                # Get a set of output for multiple files with each outputQueue item.
                # Each file has a set of output and errors to pack up for app
                for filePath, outputList, errorList in filesOutput:

                    # Synchronus callback to applicaiton
                    # Output writing and screen update occurs in this call
                    self._file_measure_callback(filePath, outputList, errorList)

                    if errorList:
                        log.file(1, "ERROR measuring: {}".format(filePath))
                        self._controlQueue.put_nowait(('JOB', 'ERROR', filePath))


    def _continue_processing(self):
        continueProcessing = True
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
                continueProcessing = False
            elif 'WORK_DONE' == myCommand:
                log.cc(2, "COMMAND: WORK_DONE")
                self._workDone = True
            for (target, command, payload) in otherCommands:
                log.cc(3, "putting {}, {}".format(target, command))
                try:
                    self._controlQueue.put((target, command, payload), True, CONTROL_QUEUE_TIMEOUT)
                except Full:
                    raise utils.JobException("FATAL EXCEPTION - Control Queue full, can't put")
        return continueProcessing


