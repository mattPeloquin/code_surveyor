#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    Code shared by surveyor components
'''

import os
import sys
import time
import string

CURRENT_FOLDER = '.'
CONSOLE_CR = "\r"

#-----------------------------------------------------------------------------
#  Exceptions

class SurveyorException(Exception):
    pass

class JobException(SurveyorException):
    pass

class InputException(SurveyorException):
    pass

class OutputException(SurveyorException):
    pass

class ConfigError(SurveyorException):
    pass

class CsModuleException(SurveyorException):
    pass

class FileMeasureError(SurveyorException):
    pass

class AbstractMethod(SurveyorException):
    def __init__(self, obj):
        self.methodName = sys._getframe(1).f_code.co_name
        self.className = obj.__class__.__name__
    def __str__(self):
        return "Abstract method called: {}.{}()".format(
            self.className, self.methodName)

#-----------------------------------------------------------------------------
# Job processing utils

@staticmethod
def _check_for_stop(self):
        for target, command, payload in otherCommands:
            log.cc(3, "putting {}, {}".format(target, command))
            try:
                self._controlQueue.put((target, command, payload), True, CONTROL_QUEUE_TIMEOUT)
            except Full:
                raise utils.JobException("FATAL EXCEPTION - Control Queue full, can't put")

#-----------------------------------------------------------------------------
#  Timing Utils

_timings = {}

def timing_start():
    timing_set('START_RUN')

def timing_elapsed():
    return timing_get('START_RUN')

def timing_set(checkpointName='DEFAULT'):
    _timings[checkpointName] = time.time()

def timing_get(checkpointName='DEFAULT'):
    return time.time() - _timings[checkpointName]

#-----------------------------------------------------------------------------
# General utils

def safe_dict_get(dictionary, keyName):
    value = None
    if dictionary is not None:
        value = dictionary.get(keyName, None)
    return value

def safe_dict_get_float(dictionary, keyName):
    try:
        return float(safe_dict_get(dictionary, keyName))
    except Exception:
        return 0.0

#-----------------------------------------------------------------------------
# String and RE utils

def get_match_string(match):
    '''
    Returns the first match string with something in it
    '''
    for matchStr in match.groups():
        if matchStr:
            return str(matchStr).strip()
    return ""

def get_match_pattern(match):
    return str(match.re.pattern)

def check_bytes_below_threshold(byteStr, chars, minWin, startPos, threshold):
    '''
    If the ratio of bytes not in chars is above the given threshold
    (within the startPos and minWin window size) return false
    '''
    #print "Bytes: {}".format(byteStr)
    isBelowThreshold = True
    bytePos = 0
    badChars = 0
    # One byte at a time, bailing if we exceed threshold
    for char in byteStr:
        bytePos += 1
        if bytePos < startPos:
            continue
        if not char in chars:
            badChars += 1
            #print "byte: {}".format(char)
        if bytePos >= minWin or bytePos == len(byteStr):
            badCharRatio = float(badChars)/float(bytePos)
            if badCharRatio > threshold:
                isBelowThreshold = False
                break
    return isBelowThreshold

def is_str_binary(byteStr):
    '''
    Default check for whether a string is binary
    '''
    windowSize = 80
    textChars = ( string.ascii_letters + string.digits + string.whitespace +
                    '~$\\/-_<>=():*|;,\"' )
    startPoint = 1
    minWindowSize = 15
    threshold = 0.2
    return not check_bytes_below_threshold(byteStr.lstrip()[:windowSize],
            textChars, minWindowSize, startPoint, threshold)

def check_start_phrases(searchString, phrases):
    '''
    Do any of the provided phrases match the start of searchString?
    '''
    phraseFound = None
    for phrase in phrases:
        if searchString.startswith(phrase):
            phraseFound = phrase
            break
    return phraseFound

def strip_null_chars(rawString):
    '''
    In 2 or 4 byte (UTF-16, UTF32) unicode conversion, null chars may be
    inserted into an Ascii string.
    TBD -- make search UTF/Unicode aware
    '''
    return rawString.replace('\00', '').replace('\n', '')

def strip_annoying_chars(rawStr):
    '''
    Get rid of annoying characters that can mess up display
    '''
    newStr = rawStr.rstrip()
    newStr = newStr.expandtabs(2)              # Make tabs consistent and small
    newStr = newStr.replace('\n', ' <\n> ')    # Avoid embedded newlines
    newStr = newStr.translate(_AnnoyingChars)   # Beeps, linefeeds, etc.
    return  newStr
_AnnoyingChars = str.maketrans(dict.fromkeys(
                    ''.join([chr(byte) for byte in range(0, 31)])))

def strip_extended_chars(rawStr):
    '''
    Get rid of binary characters
    '''
    return rawStr.translate(_ExtendedChars)
_ExtendedChars = str.maketrans(dict.fromkeys(
                    ''.join([chr(byte) for byte in range(127, 255)])))

def safe_ascii_string(byteStr):
    '''
    If the standard ASCII conversion has a Unicode error, attempt a
    unicode escaped encoding converted back to ASCII
    '''
    if byteStr is None:
        return ""
    try:
        return str(byteStr)
    except UnicodeEncodeError:
        return str(str(byteStr).encode('unicode_escape'))

def safe_utf8_string(byteStr):
    '''
    Convert a given string into a UTF8 string; if not possible,
    do an escapted convert to ASCII and then to UTF
    '''
    if byteStr is None:
        return ""
    try:
        return str(byteStr, 'utf8', 'replace')
    except UnicodeEncodeError:
        ascii = str(byteStr).encode('string_escape')
        return str(ascii)

def fit_string(fullString, maxLen, replacement="...", tailLen=None):
    '''
    Shorten strings to fit into maxlen, e.g,  "The quick brown...azy dog"
    '''
    newString = fullString
    if not maxLen <= 0 and len(newString) > maxLen:
        if not tailLen:
            tailLen = int(maxLen/2)
        replacementPos = maxLen - len(replacement) - tailLen
        shortendString = newString[:replacementPos] + replacement
        if tailLen > 0:
            shortendString += newString[-tailLen:]
        newString = shortendString
    return newString

MAX_RANK = sys.maxsize
def match_ranking_label(rankingMap, value):
    '''
    Match a ranking label to a value, based on list a of rankValue/name pairs
    where the rankValue defines the top end of the rank
    '''
    label = ""
    if not (value == ""):
        for (threshold, rank) in rankingMap:
            if float(value) <= float(threshold):
                label = rank
                break
    return label

#-----------------------------------------------------------------------------
#  File utils

def get_file_mod_time_str(filePath, dateFormat):
    # Content modification time, which st_mtime should give across all OS
    fileStats = os.stat(filePath)
    return time.strftime(dateFormat, time.localtime(fileStats.st_mtime))

def get_file_size(filePath):
    fileStats = os.stat(filePath)
    return int(fileStats.st_size)

def get_file_start(fileObject, maxWin):
    '''
    Get maxWin bytes from file
    '''
    fileObject.seek(0)
    fileStart = fileObject.read(maxWin)
    fileObject.seek(0)
    return fileStart

class SurveyorPathParser( object ):
    '''
    Provide common parsing of file paths as an object
    Upon instantiation, fill members with parsed path info
    '''
    def __init__(self, rawFilePath):

        # Remove leading slash, if any, such that the first folder position
        # will be a sub-folder. If this is a root path of a search, it is
        # represented by having an empty dirlist
        filePath = rawFilePath[1:] if rawFilePath[0] == os.sep else rawFilePath
        splitFilePath = filePath.split(os.sep)

        # Pop file name off the end of our path list
        fileName = splitFilePath.pop()
        (fileNameNoExt, fileExt) = os.path.splitext(fileName)

        # Initialize file name variations
        self.filePath = rawFilePath
        self.folder = os.path.dirname(rawFilePath)
        self.dirList = [safe_ascii_string(dirItem) for dirItem in splitFilePath]
        self.dirLength = len(self.dirList)
        self.fileName = safe_ascii_string(fileName)
        self.fileNameNoExt = safe_ascii_string(fileNameNoExt)
        self.fileExt = safe_ascii_string(fileExt)

    def __repr__(self):
        return self.dirList
    def __str__(self):
        return self.filePath

