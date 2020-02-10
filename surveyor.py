#!/usr/bin/env python3
#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Code Surveyor command line application
    See README for details
'''

import sys
import platform
import traceback
import multiprocessing
import shutil

from framework import cmdlineapp

# For Pyinstaller, it is easiest to have fake import of all csmodules
if False:
    from csmodules import *

#  Run surveyor and return status to the shell
if __name__ == '__main__':

    # Setup OS sensitive items
    printWidth = None
    try:
        currentPlatform = platform.system()

        # Try to get console width
        # Take one off to avoid line overrun
        columns, _rows = shutil.get_terminal_size(fallback=(80, 24))
        printWidth = columns - 1

        # Support multiprocessing for Windows exe
        multiprocessing.freeze_support()

    except Exception:
        # If something falls apart, try to carry on with defaults
        pass

    # Run the measurement job, always returning result to the shell
    SUCCESS = 0
    FAILURE = 1
    result = FAILURE
    try:
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
