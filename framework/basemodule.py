#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Code Surveyor Module Base Class

    Provides shared implementation for Surveyor modules to process files.
    A CS Module instance is created for each unique combination of config
    entries, and holds read-only configuration state based on those entries
    (i.e., config options are set in constructor for each instance).

    Beyond this, in terms of per-file state, CS Modules are stateless after
    each call to their external interfaces of open_file and process_file.
    These calls are not reentrant -- they may hold state while processing
    these methods and expect to complete them.

    To create a specialized module derived from this class:

        1. Identify measures and verbs to be produced in self.measures
        2. Write _measure_lines, _measure_routines, and _search_lines
           methods depending on which verbs your module will support.
        3. Place the completed file in the "csmodules" folder
        4. Module will load when requested in a config file.

    See csmodules/NBNC.py for an example.
'''

import re
import os
import filecmp
import difflib

from code_surveyor.framework import log  # No relative path to share module globals
from . import utils
from . import uistrings
from .fileopen import open_file_for_survey
from .configentry import CONFIG_TAG_PREFIX


# Fixed measurement column names
METADATA_FILENAME      = "fileName"
METADATA_FILETYPE      = "fileType"
METADATA_ABSPATH       = "fileAbsPath"
METADATA_FULLNAME      = "file.fullName"
METADATA_FILEDATE      = "file.date"
METADATA_FILESIZE      = "file.bytes"
METADATA_DIR           = "dir"
METADATA_DIRFILES      = "dir.files"
METADATA_DIRFILES_RANK = "dir.filesRank"
METADATA_MODULE        = "measure.Module"
METADATA_CONFIG        = "measure.Config"
METADATA_TIMING        = "measure.Time"

# Dupe measures are actually added by the app
METADATA_DUPE_PATH     = "dupe.firstPath"
METADATA_DUPE_FILE     = "dupe.fileName"
METADATA_DUPE_NBNC     = "dupe.nbnc"
METADATA_DUPE_DIR      = "dupe.dir"


class _BaseModule( object ):
    '''
    This class provides an inheritable implementation of the csmodule interface
    that provides robust support for file processing.
    '''
    # Config file prefixes, used in the search expressing list to identify
    # whether an expression is intended as a postive or negative match
    POS_CONFIG_PREFIX = "POSITIVE__"
    NEG_CONFIG_PREFIX = "NEGATIVE__"

    # Files in folders is based on metadate only, so process here
    SameFilesInFolderRanks = [
            ( 10, "1 to 10" ),
            ( 30, "11 to 30" ),
            ( 100, "31 to 100" ),
            ( utils.MAX_RANK, "100+" ),
            ]

    # Config-file overrideable options
    # The basemodule implements a framework for defining options that can
    # be overrideen in config files. Some of these can also be set by the
    # application
    ConfigOptions_base = {
        'FORCE_ALL_TYPES': (
            '''self._forceAll = True''',
            'Override default skipping of non-code and binary files'),
        'IGNORE_SIZE': (
            '''self._sizeThreshold = int(optValue)''',
            'Ignore files greater than the given byte size'),
        'IGNORE_PATHS': (
            '''self._ignorePaths = eval(optValue)''',
            'List of names to ignore they appear anywhere in path (no wildcards)'),
        'MEASURE_EMPTIES': (
            '''self._writeEmptyMeasures = True''',
            'Override default behavior of skipping output of empty measures'),
        'MEASURE_FILTER': (
            '''self._measureFilter = str(optValue)''',
            'Override measure filter (usually done in 3rd config column)'),
        'METADATA': (
            '''self._metaDataOpts = dict(optValue)''',
            'Add custom metadata opts (as dictionary, see basemodule.py)'),
        'METADATA_ALL': (
            '''self._metaDataOpts = {
                    'NAME': None,
                    'DIRS': 8,
                    'TAGS': None,
                    'ABSPATH':  None,
                    'FULLNAME':  None,
                    'FOLDER': None,
                    'DATE' :  ['%Y', '%m', '%d'],
                    'SIZE': None,
                    'DUPE': None,
                    }''',
            'Add all file metadata and set dir depth to 8'),
        'METADATA_DEBUG': (
            '''self._metaDataOpts['DEBUG'] = None''',
            'Add debug metadata including timing and config info'),
        'METADATA_ONLY': (
            '''self._metaDataOnly = True''',
            'Only collect metadata, do not open or measure files'),
        'DELTA_INCL_DELETED': (
            '''self._deltaIncludeDeleted = True''',
            'Include deleted lines in delta counts'),
        'CASE_SENSITIVE': (
            '''self._reFlags &= ~re.IGNORECASE''',
            'Make code searching (comments, decisions, etc.) case-sensitive'),
        }

    def __init__(self, configOptions):

        # Modules overrides to tell config validation what they can measure
        self.measures = []
        self.verbs    = []
        self.verbEnds = {}

        # Store this each measure call in case derived class wants to use
        self._currentPath = None

        # Delegate that subclasses can call to add config options
        self._configOptionDict = {}
        self._cs_init_config_options()

        # Process any config options
        for optName, optValue in configOptions:
            log.config(2, "ConfigOpt:  {}:{}".format(optName, optValue))
            try:
                configCode, _configHelp = self._configOptionDict[optName]
            except KeyError as e:
                raise utils.CsModuleException("Invalid Config Option: {}".format(str(e)))
            log.config(3, "ConfigCode:  {}".format(configCode))
            try:
                exec(configCode)
            except Exception as e:
                log.stack()
                raise utils.CsModuleException("Error executing Config Option: {}".format(str(e)))

    def _cs_init_config_options(self):
        # Add our base options of the dict that will be added to by children
        self._configOptionDict.update(self.ConfigOptions_base)

        # Options managed in the base module
        self._reFlags = re.IGNORECASE | re.VERBOSE
        self._forceAll = False
        self._ignorePaths = []
        self._sizeThreshold = 0
        self._metaDataOpts = {}
        self._metaDataOnly = False
        self._measureFilter = None
        self._writeEmptyMeasures = False
        self._deltaFilePath = None
        self._deltaIncludeDeleted = False

    @classmethod
    def _cs_config_options(cls):
        # This is called by application to get at possible options for a module
        return cls.ConfigOptions_base


    def _survey(self, linesToSurvey, configEntry, measurements, analysis):
        '''
        Abstract method that modules inheriting from basemodule overload
        to process a set of lines.
        Return value indicates whether to write the output for the
        '''
        raise utils.AbstractMethod(self)


    #-------------------------------------------------------------------------
    #  csmodule Public Interface
    #  These are the methods all csmodules must expose to the Surveyor framework

    def add_param(self, param, rawParam):
        '''
        Any config file parameters need to be processed in derived classes
        '''
        return None


    def verb_end_marker(self, verb):
        '''
        The config file loader calls this to determine closing token for
        verbs that have extra parameter lines (defined in derived classes)
        '''
        return self.verbEnds.get(verb, None)


    def open_file(self, filePath, deltaPath, existingFileHandle=None):
        '''
        Create and return a file handle, if one matches the given criteria
        Note that fileHandle may actually just be an iterable list.
        If none is returned, only file metadata will be considered.
        '''
        if self._metaDataOnly:
            return None
        for name in self._ignorePaths:
            if name in filePath:
                return None
        if deltaPath is not None:
            return self._get_delta_lines(filePath, deltaPath)
        else:
            return self._open_file(filePath, existingFileHandle)


    def process_file(self, filePath, fileLines,
                        configEntry, numSameFiles,
                        file_measured_callback):
        '''
        Inherited modules use the default implementation of process_file
        to handle calling _survey and packaging results, including any
        file metadata
        '''
        utils.timing_set('FILE_MEASURE_TIME')
        log.file(2, "process_file: {} {}".format(self.__class__.__name__, filePath))
        log.file(3, "  config: {}".format(str(configEntry)))

        # Stash path for error handling in derived classes
        self._currentPath = utils.SurveyorPathParser(filePath)

        # Does the config measure filter need to be overridden?
        if self._measureFilter is not None:
            configEntry.new_measure_filter(self._measureFilter)

        # Measurements (whole file metrics) will be stored in a dictionary
        # Pack measurement data with file metadata
        measurements = {}
        self._pack_metadata_into_measures(configEntry, numSameFiles, measurements)

        # Analysis items (per line items) are a list of dictionaries
        analysis = []

        #
        # Delegate the survey work to specializations
        #
        measureResults = {}
        analysisResults = []
        if self._survey(fileLines, configEntry, measurements, analysis):

            # Pack measurements that match our measure filter
            for measureName, measure in measurements.items():
                if self.match_measure(measureName, configEntry.measureFilters):
                    measureResults[measureName] = measure

            # Pack analysis items into a list of dictionaries for return to app
            # Only send analysis items that match filter
            for analysisItem in analysis:
                analysisRow = {}
                for itemName, itemValue in analysisItem.items():
                    if self.match_measure(itemName, configEntry.measureFilters):
                        analysisRow[itemName] = itemValue
                if analysisRow:
                    analysisResults.append(analysisRow)

            # If this is a delta comparison and there are no lines, it means the
            # delta file is an exact dupe
            if not fileLines and self._deltaFilePath:
                measureResults[METADATA_DUPE_PATH] = self._deltaFilePath

            # Add timing info
            if self.match_measure(METADATA_TIMING, configEntry.measureFilters):
                measureResults[METADATA_TIMING] = "{0:.4f}".format(utils.timing_get('FILE_MEASURE_TIME'))

        self._currentPath = None
        self._deltaFilePath = None

        # Send data back to the caller (jobworker.Worker in default framework)
        file_measured_callback(filePath, measureResults, analysisResults)

    def match_measure(self, measureName, measureFilters):
        '''
        Used to both validate config and to filter results
        Measure filters allow using * to match the end of the string.
        i.e.: size.* would match size.totallines and size.blanklines
        Also pass any measure that does not have a '.', which indicates
        it is system measure we always want to output
        '''
        if '*' in measureFilters:
            return True
        if '.' not in measureName:
            return True
        for measureFilter in measureFilters:
            match = _compare_filters(measureName, measureFilter)
            log.config(4, "Compared {} to {}: {}".format(measureName, measureFilter, match))
            if match:
                return True
        return False

    def can_do_verb(self, verbToMatch):
        return verbToMatch in self.verbs

    def can_do_measure(self, measureFilters):
        measureMatch = False
        for measure in  self.measures:
            if self.match_measure(measure, measureFilters):
                measureMatch = True
                break
        return measureMatch

    #-------------------------------------------------------------------------

    def _open_file(self, filePath, existingFile=None):
        '''
        Return fileObject if criteria are met
        Delegates reusing existing file handles to avoid overhead of 
        file open when many measures run on the same file. 
        '''
        return open_file_for_survey(filePath, existingFile, self._forceAll,
                                    self._sizeThreshold)

    def _get_delta_lines(self, filePath, deltaFilePath):
        '''
        Return a line buffer that represents additional lines relative to the
        delta path. We are not doing a full diff, only taking into account new
        files, and lines in existing files that are new/modified.
        '''
        self._deltaFilePath = deltaFilePath
        deltaLines = None
        # If no correpsonding file exists in delta, do a normal file open
        if not os.path.exists(deltaFilePath):
            log.file(1, "Delta file doesn't exist for: {}".format(deltaFilePath))
            deltaLines = self._open_file(filePath)

        # Only do a diff if there is an identical file name that has been modified
        elif not filecmp.cmp(deltaFilePath, filePath):
            fileToMeasure = self._open_file(filePath)
            if fileToMeasure is not None:
                measureFileLines = fileToMeasure.readlines()
                fileToMeasure.close()
                deltaFileLines = None
                with open(deltaFilePath, 'r') as deltaFile:
                    deltaFileLines = deltaFile.readlines()
                diffLines = difflib.unified_diff(deltaFileLines, measureFileLines)
                if diffLines:
                    deltaLines = []
                    for line in diffLines:
                        if line.startswith('+') or (self._deltaIncludeDeleted and line.startswith('-')):
                           deltaLines.append(line[2:])
            log.file(1, "{} delta lines with: {}".format(len(deltaLines), deltaFilePath))
        else:
            log.file(1, "Delta skip: {} == {}".format(filePath, deltaFilePath))
        return deltaLines

    def _pack_metadata_into_measures(self, configEntry, numSameFiles, measures):
        '''
        If there are meta-data options selected, pack the data into fileData
        '''
        for optKey, optValue in self._metaDataOpts.items():

            if optKey in ('NAME'):
                measures[METADATA_FILENAME] = self._currentPath.fileNameNoExt
                measures[METADATA_FILETYPE] = (
                        self._currentPath.fileExt if self._currentPath.fileExt else uistrings.NO_EXTENSION_NAME)

            elif optKey in ('DIRS'):
                add_dir_list_to_measures(self._currentPath, METADATA_DIR, optValue, measures)

            elif optKey in ('TAGS'):
                tagPos = 1
                for tag in configEntry.tags:
                    if tag:
                        measures[CONFIG_TAG_PREFIX + str(tagPos)] = tag
                    tagPos += 1

            elif optKey in ('DATE'):
                for dateCol in optValue:
                    suffix = ""
                    if len(optValue) > 1:
                        suffix = str(dateCol)
                    measures[METADATA_FILEDATE + suffix] = (
                            utils.get_file_mod_time_str(self._currentPath.filePath, dateCol))

            elif optKey in ('FOLDER'):
                measures[METADATA_DIRFILES] = numSameFiles
                measures[METADATA_DIRFILES_RANK] = (
                        utils.match_ranking_label(self.SameFilesInFolderRanks, numSameFiles))

            elif optKey in ('DEBUG'):
                measures[METADATA_MODULE] = self.__class__.__name__

            if optKey in ('ABSPATH', 'DUPE'):
                measures[METADATA_ABSPATH] = os.path.abspath(self._currentPath.filePath)

            if optKey in ('SIZE', 'DUPE'):
                measures[METADATA_FILESIZE] = utils.get_file_size(self._currentPath.filePath)

            if optKey in ('FULLNAME', 'DUPE'):
                measures[METADATA_FULLNAME] = self._currentPath.fileName

            if optKey in ('DEBUG', 'DUPE'):
                measures[METADATA_CONFIG] = str(configEntry)

#-----------------------------------------------------------------------------

def _compare_filters(filter1, filter2):
    match = (filter1 == filter2 or
            _compare_wildcards(filter1, filter2) or
            _compare_wildcards(filter2, filter1))
    return match

def _compare_wildcards(filter1, filter2):
    return ('*' == filter1[-1:] and
            filter2[:len(filter1) - 1] == filter1[:-1])

def add_dir_list_to_measures(path, prefix, depth, measures):
    # Pad out empty dir values
    for dirNum in range(1, depth + 1):
        if path.dirLength > dirNum:
            measures[prefix + str(dirNum)] = path.dirList[dirNum]
        else:
            measures[prefix + str(dirNum)] = ''

