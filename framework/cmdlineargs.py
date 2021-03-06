#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Code Surveyor command argument processing

    Logic for processing surveyor command line is encapsulated here.
    This code is TIGHTLY COUPLED to cmdlineapp.py and has dependencies
    on csmodule options as well.

    TBD - this code was created before argsparse in v2.7 was readily available;
    could be redone with modern v3 args, but there hasn't been a need.
'''

import os
import sys

from code_surveyor.framework import log  # No relative path to share module globals
from . import surveyor_dir
from . import utils
from .uistrings import *


# Default depth to break out path info
METADATA_MAXDEPTH_DEFAULT = 4

# The default metadata that is output
DefaultMetadata = {
        'FULLNAME':  None,
        'ABSPATH':  None,
        'NAME': None,
        'DIRS': METADATA_MAXDEPTH_DEFAULT,
        'TAGS': None,
        }

# Default maximum file size to ignore with max size option
IGNORE_SIZE_DEFAULT = 5000000

# Put max limits on things that don't strictly need limits,
# but which are silly if left unchecked
MAX_WORKERS = 256
MAX_PATH_DEPTH = 128

# Default skipping of folders and files with '.' prefix
DefaultSkip = {
    'Folders': ['.?*', 'cvs'],
    'Files': ['.*'],
    }

# Used with the -a and -ad options
MeasureAll = [("MeasureAll", 'measure NBNC file.* *')]
MeasureCode = [("MeasureCode", 'measure Code * * OPT:MEASURE_EMPTIES')]


class SurveyorCmdLineArgs( object ):

    def __init__(self, cmdArgs, surveyorApp):
        self.args = Args(cmdArgs, CMDARG_LEADS)

        self._app = surveyorApp
        self._app._jobOpt.skipFolders = DefaultSkip['Folders']
        self._app._jobOpt.skipFiles = DefaultSkip['Files']               

        # Config options to provide back to the application
        self.configCustom = None
        self.configOverrides = []
        self.ignoreSize = 0

        # Config options to provide final state to config options
        self._forceAll = False
        self._metaDataOptions = DefaultMetadata
        self._measureFilter = None
        self._inclDeletedLines = False

    def parse_args(self):
        '''
        Do simple command line parsing and set the internal state of our
        Surveyor class based on the arguments.
        For any syntax we don't recognize or help is requested, return help text.
        Otherwise return None which indicates success.
        '''
        try:
            while not self.args.finished():
                self.args.move_next()

                # Disambiguation case for measurePath/fileFilter
                # A '-' may be used to replace optional arg with path/filter
                if self.args.is_cmd() and len(self.args.get_current()) == 1:
                    if self.args.is_param_next():
                        self.args.move_next()
                        self._parse_measurement_path()
                    continue

                # Assume non-Arg is a measurePath/fileFilter definition
                elif not self.args.is_cmd():
                    self._parse_measurement_path()
                    continue

                # Our processing is based on matching first character
                fc = self.args.get_current()[1].lower()

                # Debug and profiling support
                if fc in CMDARG_DEBUG:
                    self._parse_debug_options()
                    log.msg(2, "Args: {}".format(str(self.args)))
                elif fc in CMDARG_PROFILE:
                    self._app._profiling = True
                    self._app._profileCalls = self._get_next_int(optional=True, default=self._app._profileCalls)
                    self._app._profileCalledBy = self._get_next_int(optional=True, default=self._app._profileCalledBy)
                    self._app._profileCalled = self._get_next_int(optional=True, default=self._app._profileCalled)
                    self._app._profileThreadFilter = self._get_next_str(optional=True, default=self._app._profileThreadFilter)
                    self._app._profileNameFilter = self._get_next_str(optional=True, default=self._app._profileNameFilter)

                # Config file settings
                elif fc in CMDARG_CONFIG_CUSTOM:
                    self._parse_config_options()

                # Delta path
                elif fc in CMDARG_DELTA:
                    self._parse_delta_options()

                # Duplicate processing
                # Can have an optional integer or string after this option
                elif fc in CMDARG_DUPE_PROCESSING:
                    self._app._dupeTracking = True
                    self._metaDataOptions['DUPE'] = None
                    dupeParam = self._get_next_param(optional=True)
                    try:
                        dupeParam = int(dupeParam)
                    except Exception as e:
                        pass
                    self._app._dupeThreshold = dupeParam

                # Scan and skip options
                elif fc in CMDARG_SCAN_ALL:
                    self._parse_scan_options()
                elif fc in CMDARG_SKIP:
                    self._parse_skip_options()
                elif fc in CMDARG_INCLUDE_ONLY:
                    self._app._jobOpt.includeFolders.extend(self._get_next_param().split(CMDLINE_SEPARATOR))

                # Output
                elif fc in CMDARG_METADATA == fc:
                    self._parse_metadata_options()
                elif fc in CMDARG_OUTPUT_FILTER:
                    self._measureFilter = self._get_next_str()
                elif fc in CMDARG_OUTPUT_TYPE == fc:
                    self._app._outType = self._get_next_str()
                elif fc in CMDARG_OUTPUT_FILE == fc:
                    self._parse_output_file()
                elif fc in CMDARG_SUMMARY_ONLY == fc:
                    self._app._summaryOnly = True
                elif fc in CMDARG_DETAILED == fc:
                    self._app._detailed = True
                    self._app._detailedPrintSummaryMax = self._get_next_int(
                            optional=True, default=self._app._detailedPrintSummaryMax)
                elif fc in CMDARG_PROGRESS == fc:
                    self._app._progress = True
                    self._app._printMaxWidth = self._get_next_int(
                            optional=True, default=self._app._printMaxWidth)
                elif fc in CMDARG_QUIET == fc:
                    self._app._quiet = True

                # Other options
                elif fc in CMDARG_NUM_WORKERS:
                    self._app._jobOpt.numWorkers = self._get_next_int(validRange=range(1,MAX_WORKERS))
                elif fc in CMDARG_RECURSION:
                    self._app._jobOpt.recursive = False
                elif fc in CMDARG_BREAK_ERROR:
                    self._app._jobOpt.breakOnError = True
                elif fc in CMDARG_AGGREGATES:
                    self._parse_aggregate_options()

                # Help/invalid parameter request
                else:
                    return self._parse_help_options()

            # Setup the default measurement path if not provided
            if not self._app._jobOpt.pathsToMeasure:
                self._app._jobOpt.pathsToMeasure.append(utils.CURRENT_FOLDER)

            # Setup the default config name if not provided
            if not self.configOverrides and self.configCustom is None:
                self.configCustom = CONFIG_FILE_DEFAULT_NAME


        except Args.ArgsFinishedException as e:
            raise utils.InputException(STR_ErrorParsingEnd.format(str(e)))
        else:
            log.config(4, vars(self._app))

    def config_option_list(self):
        '''
        Maps application modifiable config options to the name, value list format
        used by csmodules to process config file options
        '''
        configOptions = []
        configOptions.append(('METADATA', self._metaDataOptions))
        if self._measureFilter is not None:
            if self._measureFilter == CMDARG_OUTPUT_FILTER_METADATA:
                configOptions.append(('METADATA_ONLY', None))
                configOptions.append(('MEASURE_FILTER', '*'))
            else:
                configOptions.append(('MEASURE_FILTER', self._measureFilter))
        if self._forceAll:
            configOptions.append(('FORCE_ALL_TYPES', None))
        if self.ignoreSize > 0:
            configOptions.append(('IGNORE_SIZE', self.ignoreSize))
        if self._inclDeletedLines:
            configOptions.append(('DELTA_INCL_DELETED', None))
        return configOptions

    #-------------------------------------------------------------------------
    #  Sub-parsing for more complex options

    def _parse_measurement_path(self):
        '''
        Ensure the path we've been asked to measure is a valid directory and
        seperate the path from any file filters that was provided
        If an entry is a valid directory, we'll treat it as a request to
        measure the folder; if not, we'll treat as a file filter
        '''
        cmdLinePath = self.args.get_current()
        measurePath = cmdLinePath.rstrip('\\/')
        if not os.path.isdir(measurePath):
            filterList = measurePath.split(CMDLINE_SEPARATOR)
            requestedPath = None
            for filterItem in filterList:
                (directory, fileFilter) = os.path.split(filterItem)
                if ("" == directory) or os.path.isdir(directory):
                    self._app._jobOpt.fileFilters.append(fileFilter)
                    if requestedPath is None:
                        requestedPath = directory
                else:
                    raise utils.InputException(STR_ErrorBadPath.format(filterItem))
            if requestedPath is not None:
                measurePath = requestedPath
        if measurePath:
            self._app._jobOpt.pathsToMeasure.append(measurePath)

    def _parse_output_file(self):
        '''
        Is stdout, a dir, or a file being requested for output redirection?
        '''
        outArg = self._get_next_str()
        if os.path.isdir(outArg):
            self._app._outFileDir = outArg
        else:
            self._app._outFileOverride = True
            if 'stdout' == outArg.lower():
                self._app._outFileName = None
            else:
                outDir, self._app._outFileName = os.path.split(outArg)
                if outDir:
                    self._app._outFileDir = outDir

    def _parse_config_options(self):
        if len(self.args.get_current()) > 2:
            configOpt = self.args.get_current()[2].lower()
            if configOpt in CMDARG_CONFIG_INFO:
                self._app._jobOpt.configInfoOnly = True
                self.configCustom = self._get_next_str(optional=True, default=self.configCustom)
            # Allow config file entry to be entered on command line
            elif configOpt in CMDARG_CONFIG_CUSTOM:
                self.args.move_next()
                self.configOverrides = [
                        ("MeasureCustom", str(self.args.get_current()))]
        else:
            self.configCustom = self._get_next_str()

    def _parse_delta_options(self):
        if len(self.args.get_current()) > 2:
            configOpt = self.args.get_current()[2].lower()
            if configOpt in CMDARG_DELTA_DELETE:
                self._inclDeleted = True
        self._app._jobOpt.deltaPath = self._get_next_str()
        if not os.path.isdir(self._app._jobOpt.deltaPath):
            raise utils.OutputException(STR_ErrorBadPath.format(self._app._jobOpt.deltaPath))

    def _parse_help_options(self):
        '''
        Decide what to display for help text
        '''
        helpText = ""
        # If help is being requested, look for detailed version
        if self.args.get_current()[1].lower() in CMDARG_HELP:
            if self.args.is_param_next():
                self.args.move_next()
                helpRequest = self.args.get_current()[:1].lower()
                helpStr = STR_HelpText_Usage + self._get_detailed_help(helpRequest).format(
                                                        surveyor_dir())
                if helpRequest == CMDARG_CONFIG_CUSTOM:
                    modules = [("framework.basemodule", "basemodule", "_BaseModule")]
                    from code_surveyor import csmodules
                    for modName in csmodules.__all__:
                        modules.append(("csmodules." + modName, modName, modName))
                    for fileName, modName, className in modules:
                        moduleFile = __import__(fileName)
                        module = getattr(moduleFile, modName)
                        moduleClass = getattr(module, className)
                        optionList = list(moduleClass._cs_config_options().items())
                        if optionList:
                            helpStr += STR_HelpText_Config_OptionModName.format(modName)
                            optionList.sort()
                            for optName, optValue in optionList:
                                (optCode, optHelp) = optValue
                                helpStr += STR_HelpText_Config_OptionItemHelp.format(optName, optHelp)
                return helpStr
            else:
                return STR_HelpText_Intro + STR_HelpText_Usage + STR_HelpText_Options

        # Otherwise it is a bad arg, provide detail if available
        else:
            helpText = STR_HelpText_Usage + STR_ErrorInvalidParameter.format(
                    self.args.get_current())
            argToHelp = self.args.get_current()[:1].lower()
            helpText += self._get_detailed_help(argToHelp)
            return helpText

    def _get_detailed_help(self, helpRequest):
        try:
            return detailedHelpMap[helpRequest]
        except KeyError:
            return STR_HelpText_Options

    def _parse_scan_options(self):
        '''
        Decode the various ScanAll options
        '''
        self._forceAll = True
        self.configOverrides = MeasureAll
        self._metaDataOptions['SIZE'] = None
        self._app._detailed = True

        if len(self.args.get_current()) > 2:
            scanOpt = self.args.get_current()[2].lower()

            # Use the Code csmodule
            if scanOpt in CMDARG_SCAN_ALL_DEEP_CODE:
                self.configOverrides = MeasureCode

            # Tuning options to focus on code
            if scanOpt in CMDARG_SCAN_ALL_CODE:
                self.ignoreSize = IGNORE_SIZE_DEFAULT

            # Special case, don't open files, just do metadata
            if scanOpt in CMDARG_SCAN_ALL_METADATA:
                self._measureFilter = CMDARG_OUTPUT_FILTER_METADATA
                self._metaDataOptions['DATE'] = ['%Y', '%m', '%d']
                self._metaDataOptions['DIRS'] = METADATA_MAXDEPTH_DEFAULT

    def _parse_skip_options(self):
        '''
        Decode which skip mode and any required params
        '''
        if len(self.args.get_current()) > 2:
            skipOpt = self.args.get_current()[2].lower()
            if skipOpt in CMDARG_SKIP_DIR:
                self._app._jobOpt.skipFolders.extend(self._get_next_param().split(CMDLINE_SEPARATOR))
            elif skipOpt in CMDARG_SKIP_FILE:
                self._app._jobOpt.skipFiles.extend(self._get_next_param().split(CMDLINE_SEPARATOR))
            elif skipOpt in CMDARG_SKIP_SIZE:
                self.ignoreSize = self._get_next_int()

    def _parse_aggregate_options(self):
        '''
        Aggregate key and values are required
        There is also an optional threshold for writing the values
        '''
        keyName = self._get_next_str()
        keyValueListStr = self._get_next_param()
        if keyValueListStr.lower() == 'all':
            self._app._aggregateNames[str(keyName)] = 'all'
        else:
            self._app._aggregateNames[str(keyName)] = eval(keyValueListStr)
        thresholdKey = self._get_next_str(optional=True)
        if thresholdKey:
            self._app._aggregateThresholdKey = thresholdKey
            self._app._aggregateThreshold = self._get_next_int()

    def _parse_metadata_options(self):
        '''
        Decode metadata options, some of which have their own optional params
        '''
        fc = self._get_next_param()[0].lower()
        if fc in CMDARG_METADATA_RESET:
            # Remove all but the bare minimum metadata
            self._metaDataOptions = {}
            self._metaDataOptions['NAME'] = None
            self._metaDataOptions['TAGS'] = None
            return
        allOpts = bool(fc in CMDARG_METADATA_ALL)
        if allOpts or fc in CMDARG_METADATA_ABSPATH:
            self._metaDataOptions['ABSPATH'] = None
        if allOpts or fc in CMDARG_METADATA_FOLDER:
            self._metaDataOptions['FOLDER'] = None
        if allOpts or fc in CMDARG_METADATA_SIZE:
            self._metaDataOptions['SIZE'] = None
        if allOpts or fc in CMDARG_METADATA_DEBUG:
            self._metaDataOptions['DEBUG'] = None
        if allOpts or fc in CMDARG_METADATA_DATE:
            self._metaDataOptions['DATE'] = self._metaDataOptions.get('DATE', ['%Y'])
            if not allOpts and self.args.is_param_next():
                self.args.move_next()
                self._metaDataOptions['DATE'].append(self.args.get_current())
        if allOpts:
            self._metaDataOptions['DIRS'] = 8
        elif fc in CMDARG_METADATA_MAXDEPTH:
            self._metaDataOptions['DIRS'] = self._get_next_int(validRange=range(0, MAX_PATH_DEPTH))

    def _parse_debug_options(self):
        '''
        Decode optional level, modes, and output display length
        '''
        debugOptions = self.args.get_current()
        level = 1
        try:
            level = int(debugOptions[2])
        except (IndexError, ValueError):
            pass  # Already defaulted to debug level 1

        # Debug modes are defined by the rest of the chars
        modes = []
        debugModeMap = {
            CMDARG_DEBUG_CODE: log.MODE_NBNC,
            CMDARG_DEBUG_NOT_CODE: log.MODE_NOT_CODE,
            CMDARG_DEBUG_SEARCH: log.MODE_SEARCH,
            CMDARG_DEBUG_FILE: log.MODE_FILE,
            CMDARG_DEBUG_CONFIG: log.MODE_CONFIG,
            CMDARG_DEBUG_CONCURRENCY: log.MODE_CONCURRENCY,
            CMDARG_DEBUG_TRACE: log.MODE_TRACE,
            CMDARG_DEBUG_TEMP: log.MODE_TEMP,
            }
        charPos = 3
        while len(debugOptions) > charPos:
            curChar = debugOptions[charPos].lower()
            try:
                modes.append(debugModeMap[curChar])
            except KeyError:
                pass  # Fail silently if undefined mode
            charPos += 1

        # Output stream
        outStream = sys.stderr
        if self.args.is_param_next():
            try:
                outName = str(self.args.get_next())
                self.args.move_next()
                if not outName in ('stderr', 'stdout'):
                    outStream = open(outName, 'a', encoding='utf-8')
            except ValueError:
                pass

        # Optional max length of debug string
        printLen = self._app._printMaxWidth
        if self.args.is_param_next():
            try:
                printLen = int(self.args.get_next())
                self.args.move_next()
            except ValueError:
                pass

        # Call back to application to update debug mode
        self._app.set_logging(level, modes=modes, printLen=printLen, out=outStream)

    #-------------------------------------------------------------------------
    #  Processing argument list and setting values

    def _get_next_param(self, optional=False, default=None):
        '''
        Get next arg for an option
        Return None if optional and no param
        '''
        if not optional and not self.args.is_param_next():
            raise utils.InputException(
                    STR_ErrorParsingValueRequired.format(self.args.get_current()))
        if self.args.is_param_next():
            self.args.move_next()
            return self.args.get_current()
        else:
            return default

    def _get_next_str(self, optional=False, default=None):
        '''
        No special handling other than casting to str as of yet
        '''
        nextStr = self._get_next_param(optional, default)
        return str(nextStr) if nextStr else None

    def _get_next_int(self, default=None, validRange=None, optional=False):
        '''
        Special case for int params, we only consume if the value is an int
        so we don't collide with cases where path\file is being specified.
        Through exceptions if error conditions found
        '''
        if not optional or self.args.is_param_next():
            try:
                nextInt = int(self.args.get_next())
            except ValueError:
                if optional:
                    return default
                else:
                    raise utils.InputException(STR_ErrorParsingInt.format(
                            self.args.get_current()))

            if validRange is not None and nextInt not in validRange:
                raise utils.InputException(STR_ErrorParsingValidValue.format(
                        nextInt, self.args.get_current()))
            else:
                self.args.move_next()
                return nextInt
        else:
            return default


class Args( object ):
    '''
    This subclass encapsulates moving through the argument list items
    All knowledge about argument structure is retained by the user
    '''
    class ArgsFinishedException(Exception):
        pass

    def __init__(self, args, argDelim):
        self.argList = args
        self.argDelim = argDelim
        self.argPos = 0

    def __repr__(self):
        return "Pos: {} in {}".format(self.argPos, self.argList)

    def __str__(self):
        return " ".join(self.argList[1:])

    def move_next(self):
        if self.finished():
            raise self.ArgsFinishedException(self.get_current())
        self.argPos += 1
        log.msg(1, "Arg: {}".format(str(self.argList[self.argPos])))

    def get_next(self):
        if self.finished():
            return None
        return self.argList[self.argPos + 1]

    def get_current(self):
        assert self.argPos <= len(self.argList), "Args processing out of whack"
        return self.argList[self.argPos]

    def finished(self):
        return self.argPos >= len(self.argList) - 1

    def is_cmd(self):
        return self.get_current()[0] in self.argDelim

    def is_cmd_next(self):
        return self.get_next()[0] in self.argDelim

    def is_param_next(self):
        return not self.finished() and not self.is_cmd_next()
