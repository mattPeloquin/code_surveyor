#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    Support for modules opening files to measure
'''

import os
from codecs import BOM_UTF8, BOM_UTF16_BE, BOM_UTF16_LE, BOM_UTF32_BE, BOM_UTF32_LE

from . import log
from . import utils
from . import filetype


FILE_START_SIZE = 256

BOMS = (
    (BOM_UTF8, "UTF-8"),
    (BOM_UTF32_BE, "UTF-32-BE"),
    (BOM_UTF32_LE, "UTF-32-LE"),
    (BOM_UTF16_BE, "UTF-16-BE"),
    (BOM_UTF16_LE, "UTF-16-LE"),
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
        
    # Then check for size threshold, faster than opening file
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
    Manage the opening of the file with correct encoding based on any 
    errors in decoding utf-8 default and through inspection of file start.
    This isn't foolproof - files that use different encodings farther 
    in may blow up later if decoded, but that is rare.
    """
    fileObj = None
    start = None
    try:
        # Use buffering to reduce the cost of open on larger files
        fileObj = open(filePath, 'r', buffering=2^24, encoding='utf-8')
        start = _get_file_start(fileObj)
    except UnicodeDecodeError as e:
        if fileObj:
            fileObj.close()
        # Try to lookup Unicode BOM
        try:
            fileBinary = open(filePath, 'rb', buffering=2^8)
            startBytes = _get_file_start(fileBinary)
            bom = _check_start_phrases(startBytes, BOMS) 
            if bom:
                fileObj = open(filePath, 'r', buffering=2^24, encoding=bom)
                start = _get_file_start(fileObj)
        except Exception as e2:
            log.file(1, "Cannot open and read file: {}".format(filePath))
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


def _get_file_start(fileObj, maxWin=FILE_START_SIZE):
    fileObj.seek(0)
    fileStart = fileObj.read(maxWin)
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
