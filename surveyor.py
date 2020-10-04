#!/usr/bin/env python3
#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Code Surveyor command line application
    See README for details
'''

import os
import sys
import traceback
import multiprocessing
import shutil

SUCCESS = 0
FAILURE = 1

#  Run surveyor and return status to the shell
if __name__ == '__main__':

    # Setup OS sensitive items
    printWidth = None
    try:
        # PyInstaller support for multiprocessing and doing 
        # a fake import of csmoudles to include them in exe
        multiprocessing.freeze_support()
        if False:
            from csmodules import *

        # Try to get console width (one off to avoid line overrun)
        columns, _rows = shutil.get_terminal_size(fallback=(80, 24))
        printWidth = columns - 1
    except Exception:
        pass

    # Run the measurement job, always returning result to the shell
    result = FAILURE
    try:
        # Make sure this root path is loaded as a module to ensure 
        # framework and csmodules will load 
        sys.path.append( os.path.abspath( os.path.dirname(__file__) ) )

        from framework import cmdlineapp

        if cmdlineapp.run_job(sys.argv, sys.stdout, printWidth):
            result = SUCCESS

    except:
        print("\nA system error occurred while running Surveyor:\n")
        traceback.print_exc()
    finally:
        # Should not have child processes alive at this point, but in
        # case there was a problem, kill them to prevent hangs
        for child in multiprocessing.active_children():
            child.terminate()
            print("BAD SURVEYOR EXIT -- {} active".format(child.name))
        sys.exit(result)
