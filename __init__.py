#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    Code Surveyor

    Surveyor's design approach blends application, script, and 
    OO framework to balance several goals:

        - easy to use out of the box as a stand-alone application
        - flexibility through config files and command-line options
        - measurement customization by anyone comfortable with regex
        - easy extensibility for file processing through csmodules
        - make code internals accessible to non-Python programmers

    Surveyor has been around for a LONG time. The goal was to roughly
    follow Python idioms while striving to be generally accessible 
    (before Python became so popular). It has been solid and not needed 
    a full reworking, so is not a shining example of modern Python style.
    
    csmodules
    Holds Surveyor measurement modules. The two most important of these are:

      NBNC.py  Core per-line implementation for measuring code files. See
               comment header for a description of NBNC line logic.

      Code.py  Logic for machine-detection, routine-detection, searching,
               more detailed code measurements.

    See "csmodules\__init__.py" for a design overview.

    framework
    Contains the key abstractions and behavior.
    See "framework\__init__.py" for an overview.
'''
__version__ = '7'

