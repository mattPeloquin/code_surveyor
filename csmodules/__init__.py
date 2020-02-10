#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    csmodules -- Code Surveyor Modules

    The csmodule package is where Surveyor modules.py looks for measurement
    modules referenced in config files. Modules leverage shared code
    through implementation inheritance:

                  framework\basemodule.py
                 /                    |  \__________
           NBNC.py    searchMixin.py  |             |
               |      /           \   |       custom non-code modules
               |     /          Search.py
             Code.py_____________________________
              |       |             |            |
          Web.py  DupeLines.py  customXYZ.py    ...

    Design info for individual csmodules is in the code; NBNC.py is a good
    place to start. Some general design notes for all csmodules:

      - csmodules are Surveyor plug-ins that support both configuration options
        and code modification/extension.

      - csmodules inherit basic file handling implementation from
        framework.basemodule. This isn't strictly necessary, as long
        as a csmodule replicates the appropriate interface.

      - Unlike the Surveyor framework, error and measure output strings are
        hard-coded in the modules vs. in string resources.

      - The csmodules intentionally do not follow Python's style guidelines
        for lowercase naming to help differentiate them from generally
        callable Python modules

    Al Python modules in csmodules are loaded dynamically by the framework, so 
    are only imported in code for inheritance within this package, so
    do not need fixup of package name (will only import using the 
    csmodules absolute name vs. relative import paths). 
'''
__version__ = '7'

__all__ = [
    'NBNC',
    'Code',
    'Web',
    'Search',
    'DupeLines',
    'Depends',
    'customCobol',
    'customDelphi',
    ]


