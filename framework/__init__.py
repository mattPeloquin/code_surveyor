#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    framework -- Code Surveyor Framework

    The main relationships between the framework modules are shown below. 
    All modules utilize classes to organize most code; some modules 
    hold 2-3 closely related classes. 

               cmdlineapp.py        Presentation, dupe, aggregates
                 |     writer.py    Writes output  
             job.py                 Core application loop in main process
    jobworker.py   \                Child processes that call csmodules
           |       jobout.py        Main process thread that collects output    
     basemodule.py                  Base implementation for csmodules

    folderwalk.py   Used by job.py to walk folder tree and handle filtering
      filetype.py   Shared code for determining file types
       fileext.py   Extensions to fnmatch file filtering

   configstack.py   Interface to and caching of config information 
   configentry.py   Represents one line in a config file 
  configreader.py   Reading and parsing of config files
       modules.py   Loading and caching csmodules for configreader.py

         utils.py   General shared functionality
         log.py   Implements debug tracing functionality
     uistrings.py   Non-debug UI strings used by framework


    Concurrency
    ============
    Surveyor uses multiprocessing to partition up file processing across cores
    in a machine. Regex processing is the most expensive Surveyor activity, 
    so splitting across cores provides close to a linear gain in performance. 

    The main process thread owns the core loop (job.py) which is responsible for 
    walking all of the files in a job. It hands off groups of files as work 
    packages to child processes (jobworker.py, 1 jobworker process per core).
    The main process also spawns a separate thread (jobout.py) to collect output 
    from the jobworkers, write output file(s), and update the UI display. 
    
    Three queues are used to communicate between the 2 main process threads and
    the child processes, as diagramed below:
    
        INPUT -- Main thread puts work packages, workers process
        OUTPUT -- Workers put results, output thread grabs them
        CONTROL -- Used to handle errors, ctrl-c, and ensure clean shut down

                            SurveyorApplication
                         (creates)            \
                          /                  (callback) 
               MainProcess-Job  (spawns)->  MainProcess-OutThread 
                   (put)     \              /      (get)
                     |        \            /         |
                    INPUT     CONTROL QUEUE      OUTPUT        
                       \            |            /           
                      (get)         |        (put)
                        ChildProcesses-JobWorker 
'''
__version__ = '7'

import os
import sys
from pathlib import Path

'''
    Support relative import paths and usage of surveyor.py and framework module as 
    both run-time script and package
'''
_file = Path(__file__).resolve()
sys.path.append( str(_file.parents[2]) )
import code_surveyor.framework
__package__ = 'code_surveyor.framework'

'''
    Surveyor Dir

    A Py2Exe compiled program, sys.argv[0] will not always return fully 
    qualified path, so use sys.executable, which will.
'''

StartupPath = None

def surveyor_dir():
    '''
    Return the directory that the surveyor script was loaded from
    '''
    assert StartupPath is not None
    return StartupPath

def init_surveyor_dir(arg0):
    '''
    This must be called before calling surveyor_dir
    '''
    global StartupPath
    if running_as_exe():
        StartupPath = sys.executable
    else:
        StartupPath = arg0
    StartupPath = os.path.abspath(os.path.dirname(StartupPath))

def running_as_exe():
    '''
    If the frozen attribute is present, we're in py2exe
    otherwise we're in script
    '''
    return hasattr(sys, "frozen")

def runtime_ext():
    return "" if running_as_exe() else ".py"

def runtime_dir():
    '''
    Return the directory that the job is being run from
    Surveyor does not manipulate CWD, so we assume it is accurate
    '''
    return os.path.abspath(os.getcwd())

