
# Code Surveyor
A customizable framework for measuring and searching code files.
Provides metrics and scanning output for easy spreadsheet and pivot table analysis.

## Using Surveyor
Use Surveyor as an executeable or Python 3 script. 
Either download the appropriate version from the "dist" folder or clone this repository.
Below are some examples for running in different environments: 

    surveyor               (Surveyor executable folder in path)
    python surveyor.py     (Python in path, no .py association)
    surveyor.py            (Python and surveyor in path, .py runs)

Surveyor measures most code out of the box, but works best with custom configuration (see Config Files below).
All cores are used; use the "-w" option to modify. 

Summary metrics are displayed on the console and detailed per-file metrics are in:

    surveyor.csv

## Config Files
Surveyor measurement is driven by config files that define:

    - File types to include in the job
    - csmodules (Code Surveyor Modules) used to measure those files
    - Options to modify measurements or output

The default "surveyor.code" config file should be located with Surveyor; see this and "surveyor.examples" for documentation and eamples on how to configure Surveyor.

Each run walks the target folder tree searching for config
file(s). If no "surveyor.code" files are found the default config file is used.
Customize folder tree measurement by placing "surveyor.code" files in folders with only the measures you care about for that folder and its children. 

To exclude a folder branch, place an empty config at the top.

# NBNC Lines of Code
Surveyor's main code size metric is Non-Blank, Non-Comment (NBNC) lines. Blank lines include whitespace AND lines that have only punctuation. 
Surveyor tries to seperate machine-generated lines (see below).

The NBNC size approximation works well across languages and can be applied to other text-file human work product (like config files).

# Tips and Tricks

## "Scan All"
Although the default file has a large number of code file types, it may not map file types appropriately for your folder tree. You may not know all of the file types present in an older code base. 
Running surveyor with the "-all" option can provide a quick view of what exists in the folder tree, which can then be used to create a tuned config file.

Run with "-? a" for detailed help on this option.

## NO_EXT Extension
The NO_EXT name is used in config files for files with no extension. Surveyor skips binary files.

## Machine-generated code
Surveyor attempts to separate machine-generated code from human-written code.
This is done with Surveyor's block-detection capability and a set of regex patterns in csmodules/Code.py.
Machine-generated NBNC lines are reported under:

    file.machine

To disable machine-code detection, use the OPT:MACHINE_NONE
config file option or "-an" command line option. 
Tune regex for machine code with OPT:MACHINE_DETECTORS (see surveyor.examples).

## Performance
Performance varies depending on the size and nature of the files being measured, what measures are run, and hardware performance.
Jobs with extensive regular expression processing are likely to be CPU bound.
OS file caching will improve performance if multiple Surveyor jobs are run back-to-back. 

Surveyor optimizations include:

 - Parallel per-core processing. Files in each folder are partitioned into 
    work packages that are processed by all cores from a queue. 

 - Caching open files. Some jobs run multiple search passes on the same file,
    so contents are cached. Very large files and lines in files are skipped.

The best way to increase Surveyor job speed is to only process the files you need; only include file types you care about in your config files.

For a quick scan of all files use the "-am" option, which only looks at metadata.

# System Overview
Most design information is documented in the code itself; see specific files for descriptions of modules and classes.

Surveyor's design approach blends application, script, and OO framework to balance several goals:

    - easy to use out of the box as a stand-alone application
    - high configurability through config files and command-line options
    - measurement customization by anyone comfortable with regex
    - easy extensibility for file processing through csmodules
    - make framework internals accessible to non-Python programmers

Surveyor roughly follows Python programming idioms but is intended to be accessible and self-evident to programmers who do not have a Python background.
The design is primarily object-oriented but Surveyor code strives to have a "scriptable feel", i.e., as small as possible. 
Thus procedural approaches and/or less abstraction are used when it better achieves this goal.

## csmodules
Holds Surveyor measurement modules. The two most important of these are:

    NBNC.py -- Core per-line implementation for measuring code files. See
               it's comment header for a description of NBNC line logic.

    Code.py -- Logic for machine-detection, routine-dection, searching,
               more detailed code measurements.

See "csmodules\__init__.py" for a design overview.

## framework
Contains the key abstractions and behavior.
See "framework\__init__.py" for an overview.

Copyright (c) 2004-2019 Matt Peloquin and Construx Software
