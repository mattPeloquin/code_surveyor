#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    Support for modules opening files to measure.

    Based on testing, for performance surveyor tries to open files as 
    decoded text vs. doing a binary read and decoding each line. 
    To do this each file is pre-read into a buffer as UTF8, and 
    if problems are encountered, other decoding is applied. 
    This can fail if the file has decoding issues past the 
    FILE_START_UTF8_CHECK size.
'''

import os
from codecs import ( BOM_UTF8, BOM_UTF16, BOM_UTF32, 
        BOM_UTF16_BE, BOM_UTF16_LE, BOM_UTF32_BE, BOM_UTF32_LE )

from . import log
from . import utils
from . import filetype

# How much of the file to read to test UTF8 decoding
FILE_START_UTF8_CHECK = 2 ** 18

# How much of file to read to support checks of content
FILE_START_CHECK = 256

FILE_BUFFERING = 2 ** 24

# Registered file type encodings detected with start of file bytes
BOMS = (
    (BOM_UTF8, "utf_8"),
    (BOM_UTF32, "utf_32"),
    (BOM_UTF32_BE, "utf_32_be"),
    (BOM_UTF32_LE, "utf_32_le"),
    (BOM_UTF16, "utf_16"),
    (BOM_UTF16_BE, "utf_16_be"),
    (BOM_UTF16_LE, "utf_16_le"),
    )

# Magic numbers and phrases
NonCodeFileStart = (
    ('\x7ELF', 'ELF'), 
    ('PK\x03\x04', 'ZIP'),      
    ('\x1F\x8B\x08', 'Gzip'),  
    )


def open_file_for_survey(filePath, existingFile, forceAll, sizeThreshold):
    '''
    Includes logic for handling different file encodings and 
    options for skipping files based on different detections
    of content in the file.
    existingFile is used as optimization to prevent reopening
    a file multiple times.
    '''
    # Check extensions first, since already have data
    if not forceAll and filetype.is_noncode_ext(filePath):
        log.file(1, "Skipping, non-code ext: {}".format(filePath))
        return 
        
    # Then check for size threshold; faster than opening file
    if sizeThreshold > 0:
        fileSize = utils.get_file_size(filePath)
        if sizeThreshold < fileSize:
            log.file(1, "Skipping, size {}: {}".format(fileSize, filePath))
            return

    # Reset an existing file, or open a new one
    if existingFile:
        existingFile.seek(0)   
        rv = existingFile
    else:
        rv = _open_file( filePath, forceAll )
    return rv

def _open_file(filePath, forceAll):
    """
    Manage the file opening with correct encoding based on any errors in 
    decoding utf-8 default and through inspection of file start.
    This isn't foolproof - files that use different encodings farther 
    in may blow up later if decoded, but that is rare.
    """

    # Use buffering to reduce the cost of open on larger files
    fileObj = open(filePath, 'r', buffering=FILE_BUFFERING, encoding='utf_8')

    # OPTION - read the file as binary and let the modules 
    # do the decoding
    #return open(filePath, 'rb', buffering=FILE_BUFFERING)

    # Grab the first bytes of the file
    start = None
    try:

        start = _get_file_start(fileObj, FILE_START_UTF8_CHECK)

    except UnicodeDecodeError as e:
        fileObj.close()
        try:
            # Try lookup of known BOMs
            # Otherwise open with safe 1-byte ascii decoding 
            fileBinary = open(filePath, 'rb', buffering=FILE_START_CHECK)
            startBytes = _get_file_start(fileBinary, FILE_START_CHECK)
            encoding = _check_start_phrases(startBytes, BOMS) or 'latin_1'
            log.file(1, "UTF-8 error, trying {}: {}".format(encoding, filePath))
            fileObj = open(filePath, 'r', buffering=FILE_BUFFERING, 
                            encoding=encoding)
            start = _get_file_start(fileObj, FILE_START_CHECK)
        except Exception as e2:
            log.msg(1, "Cannot open and read file: {}".format(filePath))
            fileObj.close()
        finally:
            fileBinary.close()
 
    # Do tests that look at start of the file
    if start:
        keepFileOpen = forceAll
        if not forceAll:
            if _is_noncode_file(start):
                log.file(1, "Skipping, non-code start: {}".format(filePath))
            elif not filetype.is_text_file(start):
                log.file(1, "Skipping, binary char: {}".format(filePath))
            else:
                keepFileOpen = True
        if not keepFileOpen:
            fileObj.close()
            fileObj = None
    else:
        fileObj = None

    return fileObj

def _get_file_start(fileObj, maxWin):
    fileObj.seek(0)
    fileStart = utils.safe_string(fileObj.read(maxWin))
    fileObj.seek(0)
    return fileStart

def _is_noncode_file(fileStart):
    # Look for known magic numbers and phrases in file start
    phraseFound = _check_start_phrases(fileStart, NonCodeFileStart)
    return phraseFound is not None

def _check_start_phrases(start, phrases):
    '''
    Do any of the provided phrases match the start of searchString?
    '''
    phraseFound = None
    for phrase, result in phrases:
        if start.startswith(phrase):
            phraseFound = result
            break
    return phraseFound
