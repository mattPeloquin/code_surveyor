#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Surveyor Logging Support
    Provides support for instrumenting surveyor with both application-specific
    tracing that can be tailoerd by level and modes and Python method tracing
'''

import os
import sys
import types
import logging
import traceback
import threading
import multiprocessing

from . import utils
from . import job

#-----------------------------------------------------------------
#  Public Interface

# Public log methods, default to empty for performance
# Python won't optimize away code passed to arguments, so doing things 
# like string formatting in the msg argument can be expensive
def msg(level, msg): pass
def file(level, msg):  pass
def config(level, msg):  pass
def cc(level, msg):  pass
def code(level, msg): pass
def notcode(level, msg): pass
def search(level, msg):  pass
def temp(level, msg):  pass
def stack(level=1): pass

MODE_NBNC = 'nbnc'
MODE_NOT_CODE = 'not_code'
MODE_SEARCH = 'search'
MODE_FILE = 'file'
MODE_CONFIG = 'config'
MODE_CONCURRENCY = 'concurrency'
MODE_TRACE = 'python_trace'
MODE_TEMP = 'temp'

DEFAULT_PRINT_WIDTH = 78

# The main process sets up context that it can pass to children
def init_context(level, modes=[], printLen=DEFAULT_PRINT_WIDTH, 
                    out=None, lock=None):
    global _level, _modes, _printLen, _writer
    _level = int(level)
    print( _level )
    _modes = list(modes)
    _printLen = int(printLen)
    _writer = DebugWriter(lock, out)
    _init()

def get_context():
    if _level > 0:
        return (_level, _modes, _printLen,
                _writer.out.name, _writer.lock)
    else:
        return (_level, _modes, None, None, None)

def set_context(context):
    global _level, _modes, _printLen, _writer
    (_level, _modes, _printLen, out, lock) = context
    if _level > 0:
        _writer = DebugWriter(lock, out)
        _init()
    if MODE_CONCURRENCY in _modes:
        multiprocessing.util.log_to_stderr(logging.INFO)
        if _level > 2:
            multiprocessing.util.log_to_stderr(logging.DEBUG)

# Accessors
def level():
    return _level
def modes():    
    return _modes
def out():      
    return None if _writer is None else _writer.out


#-----------------------------------------------------------------
#  Global State

_level = 0

# This controls "modes" used to differentiate different groupings
# of tracking. More than one mode can be active in a session
_modes = []

# The writer object determines what to write to
_writer = None

# Max str width for debug trace lines
_printLen = 0

# Keep track of last puthon trace string that was output, to avoid dupes
_lastPythonTraceString = None


#-----------------------------------------------------------------
#  Surveyor Trace Methods

def _init():
    _add_debug_funcs()
    try:
        if MODE_TRACE in modes():
            sys.settrace(_python_trace_on)
        else:
            sys.settrace(_python_trace_off)
    except:
        sys.stdout.write("\n\nsettrace call failed, no Python tracing available\n\n")

# For perfomance, assign the default empty functions to pass, and only
# reassign when tracing has been initialized
_traceMethods = set(['msg', 'file', 'config', 'cc',
        'code', 'notcode', 'search', 'temp', 'enum', 'stack', ])
def _add_debug_funcs():
    for (key, value) in globals().items():
        if key in _traceMethods:
            globals()[key] = globals()['_' + key]

# Real trace functions
def _msg(level, msg):       _debug_log(level, msg)
def _file(level, msg):      _debug_log_mode(level, msg, MODE_FILE)
def _config(level, msg):    _debug_log_mode(level, msg, MODE_CONFIG)
def _cc(level, msg):        _debug_log_mode(level, msg, MODE_CONCURRENCY)
def _code(level, msg):      _debug_log_mode(level, msg, MODE_NBNC)
def _notcode(level, msg):   _debug_log_mode(level, msg, MODE_NOT_CODE)
def _search(level, msg):    _debug_log_mode(level, msg, MODE_SEARCH)
def _temp(level, msg):      _debug_log_mode(level, msg, MODE_TEMP)

def _stack(level=1):
    if _level >= level:
        _debug_log_raw("\n\nERROR -- Stack Traceback below:\n{}".format(
            traceback.format_exc()))

# Helpers
def _debug_log_mode(level, msg, debugMode):
    if debugMode in _modes:
        _debug_log(level, msg)

def _debug_log(level, msg):
    if isinstance(msg, str):
        _debug_write(level, msg)
    elif type(msg) == types.FunctionType:
        _debug_write(level, msg())
    else:
        try:
            try:
                for key, value in obj.items():
                    _debug_write(level, "  " + str(key) + ": " + str(value))
            except AttributeError:
                for item in obj:
                    _debug_write(level, "  " + str(item))
        except Exception:
            _debug_write(level, str(msg))

def _debug_write(level, msg):
    if _level >= level:
        _writer.write_msg(msg)

def _debug_log_raw(msg):
    _writer.write_msg(msg, noLock=True, noTruncate=True, noStrip=True)


#-----------------------------------------------------------------
#  All debug output occurs through this object, which fronts an output
#  stream or file and handles concurrency locking
class DebugWriter( object ):
    def __init__(self, lock, out=None):
        try:
            if isinstance(out, basestring):
                # Open as append since the file can be shared by processes
                outStream = open(out, 'a', encoding='utf-8')
            elif outStream is None:
                outStream = sys.stderr
            else:
                outStream = out
        except Exception:
            outStream = sys.stderr
        self.out = outStream
        # The Lock needs to be shared with threads/processes
        # to ensure coherent output streams
        self.lock = lock

    def write_msg(self, msg, noLock=False, noTruncate=False, noStrip=False):
        try:
            lockAquired = False
            if msg is not None:
                if not noStrip:
                    msg = utils.safe_string(msg)
                    msg = utils.strip_annoying_chars(msg)

                processName = multiprocessing.current_process().name
                threadName = threading.current_thread().name
                prefix = "Main"
                if processName != "MainProcess":
                    prefix = processName
                elif threadName != "MainThread":
                    prefix = threadName
                msg = "{}> {}\n".format(prefix, msg)

                if not noTruncate:
                    msg = utils.fit_string(msg, _printLen, " /.../ ")

                if not noLock and self.lock is not None:
                    lockAquired = self.lock.acquire( timeout=job.JOB_EXIT_TIMEOUT )
                
                self.out.write(msg)
                self.out.flush()

        except:
            sys.stdout.write("ERROR> Exception thrown in DebugWriter")
            traceback.print_exc()
            raise
        finally:
            if lockAquired:
                self.lock.release()


#-----------------------------------------------------------------
#  Python Tracing Support
#
#  Support different filtering levels on Python tracing
#  Prevent circular references and deadlocks by not allowing tracing
#  on this file or trace methods, and not using the display lock when
#  doing per-routine tracing.

IGNORE_FILES = ['trace.py']
IGNORE_ROUTINES = ['_trace', 'write']

def _python_trace_off(frame, event, arg):
    return

def _python_trace_on(frame, event, arg):
    if event == 'call':
        try:
            caller = frame.f_back
            codeObject = frame.f_code
            routineLine = frame.f_lineno
            return _python_call_trace(codeObject, routineLine, caller)
        except:
            # Bail if we don't have valid context; can happen during shutdown
            return

def _python_call_trace(codeObject, routineLine, caller):
    routineName = codeObject.co_name
    routineFilePath = codeObject.co_filename
    routinePath, routineFile = os.path.split(routineFilePath)

    if _trace_this_routine(routineName, routineFile):
        callerName = caller.f_code.co_name
        callerLine = caller.f_lineno
        callerFilePath = caller.f_code.co_filename
        callerPath, callerFile = os.path.split(callerFilePath)

        if _trace_this_routine(callerName, callerFile):
            # For _level 1, trace Surveyor module calls, eating duplicates
            if _level > 0 and _is_surveyor_file(routineFilePath):
                traceString = " >> ({1}) ==> ({0})".format(routineFile, callerFile)
                global _lastPythonTraceString
                if _lastPythonTraceString != traceString:
                    _debug_log(_level, traceString)
                    _lastPythonTraceString = traceString

            # For _level 2, trace of Surveyor method calls
            # For _level 3, add Surveyor calls to Python
            if (_level > 1 and _is_surveyor_file(routineFilePath) or
                    _level > 2 and _is_surveyor_file(callerFilePath)):
                _writer.write_msg(
                        " >> ({4}:{5}){3} ==> ({1}:{2}){0}".format(
                                routineName, routineFile, routineLine,
                                callerName, callerFile, callerLine),
                        noLock=True)

            # For _level 4, add all calls and file names
            elif _level > 3:
                _writer.write_msg(
                        " >> {5}:({4}){3} ==> {2}:({1}){0}".format(
                                routineName, routineLine, routineFilePath,
                                callerName, callerLine, callerFilePath),
                        noLock=True)

def _trace_this_routine(routineName, path):
    _filePath, fileName = os.path.split(path)
    if fileName in IGNORE_FILES:
        return False
    for routineStart in IGNORE_ROUTINES:
        if routineName.startswith(routineStart):
            return False
    return True

def _is_surveyor_file(path):
    path.lower()
    return "surveyor" in path


