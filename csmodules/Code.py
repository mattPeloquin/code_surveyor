#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Main Surveyor module for detailed code analysis
'''

import re
import sys
import zlib

from framework import utils
from framework import log
from framework import basemodule
from .NBNC import NBNC
from .searchMixin import _searchMixin


class Code( _searchMixin, NBNC ):
    '''
    Extends behavior of NBNC to support machine/content detection, searching of
    code, routine detection, and complexity metrics.

    Human vs. Machine Code
    By default Code records most metrics only for lines identified
    in the "HUMAN_CODE" block, even though they are tracked for every block.
    This can overridden in derived classes (see Web for an example).

    Per-Routine Complexity
    The "routines" verb is used to provide per-routine measurement, with
    routine detection occuring using regex search matches for routine start.
    Approximated cyclomatic complexity metrics are calculated by counting
    keywords for branches or analagous complexity in routines (including SQL).
    Decisions, case, boolean logic, and branchings (returns/breaks/goto)
    are reported as separte metrics.
    "Complexity" is by default the sum of decisions, cases, and branchings.

    Search
    Implements searching for either code OR comments -- if you want to search
    an entire file, use the Search module. See the Search module for
    instructions on how to set up positive and negative searches.

    In-Line Comments
    Adds detection of inline comments, and includes them in comment count.
    This means file.comment may retern different results than the NBNC
    module, and lines with inline comments will be counted twice as
    both code and comment (can be overridden).
    '''
    VERB_ANALYZE = "analyze"
    VERB_SEARCH      = "search"
    VERB_SEARCH_END  = "search_end"
    VERB_ROUTINES     = "routines"
    VERB_ROUTINES_END = "routines_end"
    VERB_TEMPLATE_MEASURE     = "tempmeasure"
    VERB_TEMPLATE_MEASURE_END = "tempmeasure_end"

    LINES_MACHINE       = "file.machine"
    LINES_RAW           = "file.rawTotal"
    LINES_IGNORED       = "file.ignored"
    LINES_BLANK         = "file.blank"
    LINES_FAUX_BLANK    = "file.blankFaux"
    LINES_TRUE_BLANK    = "file.blankTrue"
    LINES_TEMPLATE      = "file.template"
    LINES_DEADCODE      = "file.dead"
    LINES_CONTENT       = "file.content"
    LINES_CODE_CONTENT  = "file.code+content"
    CODE_FILESIZE_RANK  = "file.nbncRank"
    CODE_COMMENT_RANK   = "file.commentRank"
    FILE_CRC            = "file.crc"

    CODE_IMPORTS        = "nbnc.imports"
    CODE_DECISIONS      = "nbnc.decisions"
    CODE_IMPORT_RANK    = "nbnc.importRank"
    CODE_ASM_COMMENTS   = "nbnc.inlineComments"
    CODE_CLASSES        = "nbnc.classes"
    CODE_ROUTINES       = "nbnc.routines"
    CODE_SEMICOLON      = "nbnc.semicolons"
    CODE_PREPROCESSOR   = "nbnc.preprocessor"
    CODE_BYTE_RATIO     = "nbnc.byteRatio"
    CODE_CRC            = "nbnc.crc"

    SEARCH_TOTAL_PREFIX = "search."
    SEARCH_MATCH        = "search.match"
    SEARCH_LINE         = "search.line"
    SEARCH_LINENUM      = "search.linenum"
    SEARCH_CONFIG_RE    = "search.regex"
    SEARCH_REGEXP       = "search.regex-full"

    ROUTINE_NAME            = "routine.name"
    ROUTINE_LINE            = "routine.line"
    ROUTINE_LINENUM         = "routine.lineNum"
    ROUTINE_LINECOL         = "routine.lineCol"
    ROUTINE_LINEINDENT      = "routine.lineNesting"
    ROUTINE_CONFIG_RE       = "routine.regex"
    ROUTINE_REGEX           = "routine.regex-full"
    ROUTINE_NBNC            = "routine.nbnc"
    ROUTINE_NBNC_RANK       = "routine.nbncRank"
    ROUTINE_COMMENTS        = "routine.comments"
    ROUTINE_COMMENTS_RANK   = "routine.commentsRank"
    ROUTINE_COMPLEXITY      = "routine.complexity"
    ROUTINE_COMPLEXITY_RANK = "routine.complexityRank"
    ROUTINE_MAXINDENT       = "routine.maxNesting"
    ROUTINE_MAXINDENT_RANK  = "routine.maxNestingRank"
    ROUTINE_DECISIONS       = "routine.c-decisions"
    ROUTINE_CASES           = "routine.c-cases"
    ROUTINE_BOOLEANS        = "routine.c-booleans"
    ROUTINE_BRANCHINGS      = "routine.c-escapes"

    # Measurement ranking
    CommentDensityRanks = [
            ( 0, "0%" ),
            ( 4, "> 25%" ),
            ( 10, "> 10%" ),
            ( 20, "> 5%" ),
            ( utils.MAX_RANK, "< 5%" ),
            ]
    FileSizeRanks = [
            ( 200, "1 to 200" ),
            ( 600, "201 to 600" ),
            ( 1800, "601 to 1800" ),
            ( utils.MAX_RANK, "1800+" ),
            ]
    ImportRanks = [
            ( 4, "0 to 4" ),
            ( 10, "5 to 10" ),
            ( 20, "10 to 20" ),
            ( utils.MAX_RANK, "21+" ),
            ]
    RoutineSizeRanks = [
            ( 50, "1 to 50" ),
            ( 100, "51 to 100" ),
            ( 200, "101 to 200" ),
            ( utils.MAX_RANK, "200+" ),
            ]
    RoutineComplexityRanks = [
            ( 6, "1 to 6" ),
            ( 14, "7 to 14" ),
            ( 30, "15 to 30" ),
            ( utils.MAX_RANK, "31+" ),
            ]
    MaxNestingRanks = [
            ( 2, "0 to 2" ),
            ( 5, "3 to 4" ),
            ( utils.MAX_RANK, "5+" ),
            ]

    # Friendly names for the detector blocks
    HUMAN_CODE = 0
    MACHINE = 1
    CONTENT = 2

    # Nesting depth tuning
    ROUTINE_NESTING_INDENT = 4
    ROUTINE_IGNORE_COLUMN = 20

    # Options that can be provided in configuraiton files
    ConfigOptions_Code = {
        'BLOCK_IGNORE': (
            '''self.blockChangeIgnore = str(optValue)''',
            'Ignore block change detection if line contains string'),
        'BLOCK_IGNORE_FILE': (
            '''self.blockIgnoreFile = str(optValue)''',
            'Stop block change detection if line contains string'),
        'MACHINE_NONE': (
            '''self.blockDetectors[self.MACHINE] = []''',
            'Turn off machine detection'),
        'MACHINE_ALL': (
            '''self.blockDetectors[self.MACHINE] = [[re.compile(r'.*',re.IGNORECASE),None]]''',
            'Entire file is considered machine code'),
        'MACHINE_MEASURE': (
            '''self._measureBlock = self.MACHINE''',
            'Measures machine code block instead of human-written'),
        'MACHINE_ADD_DETECT': (
            '''self.blockDetectors[self.MACHINE].append(eval(optValue))''',
            'Add a machine detection regex block'),
        'MACHINE_DETECTORS': (
            '''self.blockDetectors[self.MACHINE] = eval(optValue)''',
            'Completey replace machine detction regex blocks'),
        'CONTENT_ADD_DETECTOR': (
            '''self.blockDetectors[self.CONTENT].append(eval(optValue))''',
            'Add a content detection regex'),
        'CONTENT_DETECTORS': (
            '''self.blockDetectors[self.CONTENT] = eval(optValue)''',
            'Completely replace content detection regex blocks'),
        'BOOLEANS': (
            '''self.reBooleans = re.compile(optValue, self._reFlags)''',
            'Override the regex used to detect boolean decisions'),
        'SEARCH_STRINGS': (
            '''self._includeStringContent = True''',
            'Include string content in searches and other processing'),
        'SEARCH_COMMENTS': (
            '''self._includeComments = True''',
            'Include comment lines in searches and other processing'),
        'ONLY_COMMENTS': (
            '''self._onlyComments = True''',
            'Only consider comment lines in searches and other processing'),
        'INLINE_EXCLUDE': (
            '''self._commentsInclInline = False''',
            'file.comment will exclude in-line assembly style comments'),
        'INLINE_INCL_QUOTE': (
            '''self.inlineCommentMatches.append("'")''',
            'Single quote on a line will count for an in-line comment'),
        'INLINE': (
            '''self.inlineCommentMatches = eval(optValue)''',
            'Override inline comment detection, as list'),
        'COMP_INCL_BOOLEAN': (
            '''self._complexityInclBooleans = True''',
            'routine.complexity will include boolean decisions'),
        'COMP_EXCL_ESCAPES': (
            '''self._complexityInclEscapes = False''',
            'routine.complexity exclude return, break, continue, except, goto'),
        'COMP_EXCL_CASES': (
            '''self._complexityInclCases = False''',
            'routine.complexity will exclude case statements'),
        'DECISIONS': (
            '''self.reDecision = re.compile(optValue, self._reFlags)''',
            'Override the default decision regex'),
        'DEADCODE_NONE': (
            '''self._inclDeadCode = False''',
            'Turn off dead code detection'),
        'DEADCODE': (
            '''self.reDeadCode = re.compile(optValue, self._reFlags)''',
            'Override the regex used to detect code in comments'),
        'IMPORTS': (
            '''self.reImports = re.compile(optValue, self._reFlags)''',
            'Override the regex used to detect imports'),
        'PREPROCESSOR': (
            '''self.rePreprocessor = re.compile(optValue, self._reFlags)''',
            'Override the regex used to detect preprocessor lines'),
        'ROUTINES': (
            '''self.reDefaultRoutine = re.compile(optValue, self._reFlags)''',
            'Override the regex used to detect routine starts'),
        'ROUTINE_FILE_LINES': (
            '''self.routineInclFileLines = True''',
            'Capture groups of lines outside routines as routines'),
        'ROUTINE_SPAN_BLOCKS': (
            '''self._routineSpanBlocks = True''',
            'Allow routine measurements to span blocks (use with caution)'),
        'ROUTINE_SINGLE_LINE': (
            '''self._routineSingleLine = True''',
            'Make grouped each routine line starts count as routines'),
        'ROUTINE_OUTPUT_SINGLE': (
            '''self._routineOutputSingle = True''',
            '''Normally don't include single-line routine hits in output'''),
        'ROUTINE_NESTING_INDENT': (
            '''self.routineAvgIndent = int(optValue)''',
            'Spaces for each code indent, default: 1 indent = ' +
                    str(ROUTINE_NESTING_INDENT) + ' spaces'),
        'ROUTINE_IGNORE_COLUMN': (
            '''self.routineIgnoreCol = int(optValue)''',
            'If non-zero, ignore nested routines after column ' + str(ROUTINE_IGNORE_COLUMN)),
        'CLASSES': (
            '''self.reClass = re.compile(optValue, self._reFlags)''',
            'Override the regex used to detect classes'),
        'ESCAPES': (
            '''self.reEscapes = re.compile(optValue, self._reFlags)''',
            'Regex for escape keywords (return, continue, break, goto, catch)'),
        'CASES': (
            '''self.reCases = re.compile(optValue, self._reFlags)''',
            'Override the regex used to case statements'),
        }

    #-------------------------------------------------------------------------

    def __init__(self, options):
        super(Code, self).__init__(options)
        self.verbs = [
                self.VERB_TEMPLATE_MEASURE,
                self.VERB_MEASURE,
                self.VERB_ROUTINES,
                self.VERB_SEARCH,
                self.VERB_ANALYZE,
                ]
        self.verbEnds = {
                self.VERB_TEMPLATE_MEASURE: self.VERB_TEMPLATE_MEASURE_END,
                self.VERB_ROUTINES: self.VERB_ROUTINES_END,
                self.VERB_SEARCH: self.VERB_SEARCH_END,
                }
        self.measures = [ "file.*", "nbnc.*", "search.*", "routine.*" ]

    @classmethod
    def _cs_config_options(cls):
        return cls.ConfigOptions_Code

    def _cs_init_config_options(self):
        super(Code, self)._cs_init_config_options()
        self._configOptionDict.update(self.ConfigOptions_Code)
        self._configOptionDict.update(self.ConfigOptions_Search)

        # Default behavior is to focus metrics on the human-written code
        self._measureBlock = self.HUMAN_CODE

        #
        # Expressions for detecting blocks
        #
        self.blockDetectors = [

            # Block Detector 0 -- Human Code
            # Default file content is assummed to be human-written code
            [],

            # Block Detector 1 -- Machine Generated
            # Generated code is considered anything appearing in list items below
            # The first element of each lists identifies the block start
            # The second element the end; if None, block goes to end of file
            [
                # This will catch .NET and similar code blocks
                [   re.compile( r'''region \b .*? \b generated''', self._reFlags ),
                    re.compile( r'''end \s* region''', self._reFlags ) ],

                # Phrases often used by different tools to identify an entire
                # file as generated
                [   re.compile( r'''\b do \s+ not \s+ ( edit | modify ) \b''',
                            self._reFlags),
                    None ],
                [   re.compile( r'''
                            ( generated | compiled ) \b [^\.]*? \b
                            ( with | by | from | date | time | auto |
                                    code | file | class | script | source ) .* $
                            ''', self._reFlags),
                    None ],
                [   re.compile( r'''
                            \b ( auto[^\b]*? | code | file | class | script | source | designer ) \b [^\.]*? \b
                            ( generated | \bcreated ) \b''', self._reFlags),
                    None ],
                [   re.compile( r'''
                            \b created \b .*? \b ( tool | auto | code | script ) \b .* $
                            ''', self._reFlags),
                    None ],
            ],

            # Block Detector 2 -- Content
            # No default content detection, derived classes and options can add detectors
            [],
        ]

        # Default Complexity Metrics
        # Look at decision keywords, case statements, brandching, and booleans.
        # The "complexity" metrics is an aggregate that includeds decisions +
        # some of the others, as per the _complexityInclXxx flags
        self.reDecision = re.compile(r'''
                \b ( if | elseif | elif | else | unless |
                for | foreach | while | until |
                when | from | where | join | find
                ) \b ''',
                self._reFlags)
        self._complexityInclCases = True
        self.reCases = re.compile(
                r' \b (case) \b ',
                self._reFlags)
        self._complexityInclEscapes = True
        self.reEscapes = re.compile(
                r' \b (return | continue | break | goto | except | catch | finally) \b ',
                self._reFlags)
        self._complexityInclBooleans = False
        self.reBooleans = re.compile(
                r' ( \s+ and \s+ | \s+ or \s+ | \|\| | \&\& )',
                self._reFlags)

        # Routine options
        self.routineInclFileLines = False
        self._routineSpanBlocks = False
        self._routineSingleLine = False
        self._routinePrevLineStart = False
        self._routineOutputSingle = False

        # Commented-out "Dead Code" detector:
        #   lines ending in semicolon, continuation
        #   common code-only characters on a line
        #   a period sandwhiched beteween two words
        #   = without <> (avoid false neg on doc metadata)
        self._inclDeadCode = True
        self.reDeadCode = re.compile(
                r' [;{}_\[\]\(]+\s*$ | [A-Za-z]\.[A-Za-z] | [&\+\[\]\|]+ | [=]+ (?![^>]) ',
                self._reFlags)

        # Preprocessor lines
        self.rePreprocessor = re.compile(
                r' ^ \s* [#]( def | if | else | end ) ',
                self._reFlags)

        # Template matching
        self._matchTemplateLines = False

        # Inline assembler style comment detector
        # Count inline comments and also remove them for some types of searches
        self._commentsInclInline = True
        self.inlineCommentMatches = [ '//', '[#](?!def|inc|if)', '/*' ]

        # Imports
        # Perl "use" and "require" tend to be very noisy, so can be added
        # via OPT:IMPORT in the config file
        self.reImports = re.compile(
                r' \b (using | import | [#]* include) \b ',
                self._reFlags)

        # Generic class detector
        # Tune in OPT:CLASSES if this is an important metric
        self.reClass = re.compile(
                r' \b (class | type | interface) \b ',
                self._reFlags)

        # Generic routine detector
        # These will work as rough estimates -- tune them for your specific
        # language if this is an important per-file metric
        # The more detailed per-routine analysis found in surveyor.examples will
        # usually work better to provide routine analysis
        self.reDefaultRoutine = re.compile(r'''
                \b (def|public|private|protected|static|void|sub|func|function|
                    prop|property|proc|procedure) \s* [\( \[ { ]+ ''',
                self._reFlags)

        # Code nesting factors
        # An approximation of nesting is based on the indentation of each line.
        self.routineAvgIndent = self.ROUTINE_NESTING_INDENT
        self.routineIgnoreCol = self.ROUTINE_IGNORE_COLUMN

        # Options to allow searching and in comments or string literals
        self._includeComments = False
        self._onlyComments = False
        self._includeStringContent = False

    #-------------------------------------------------------------------------
    #  Pre and Post processing for each file

    def _survey_start(self, params):
        super(Code, self)._survey_start(params)
        self._reset_routine_counts()

        # Track whether the start of a routine has been encountered
        # Reset after each block transition, since routines don't cross blocks
        self._foundFirstRoutineSinceTransition = False

        # Zero out value counts for items counted
        num_detectors = len(self.blockDetectors)
        self.counts['Imports']          = [0] * num_detectors
        self.counts['Classes']          = [0] * num_detectors
        self.counts['Routines']         = [0] * num_detectors
        self.counts['Decisions']        = [0] * num_detectors
        self.counts['DeadCode']         = [0] * num_detectors
        self.counts['TemplateLines']    = [0] * num_detectors
        self.counts['AsmComments']      = [0] * num_detectors
        self.counts['TotalSearchHits']  = [0] * num_detectors
        self.counts['Semicolons']       = [0] * num_detectors
        self.counts['Preprocessor']     = [0] * num_detectors
        self.counts['nbncCRC']          = [0] * num_detectors
        self.totalNbncAtLastRoutine     = [0] * num_detectors
        self.totalCommentsAtLastRoutine = [0] * num_detectors

        # Put any search strings into our search dictionaries
        self._positiveSearches, self._negativeSearches = self._setup_search_strings(params)

        # Track a file-CRC based on all lines
        self._fileCrc = 0

    def _survey_end(self, measurements, analysis):
        '''
        Package up metrics from this file to send back to caller
        Completely override the NBNC implementaiton
        '''
        self._save_measures(measurements)

        # Capture information for the last routine (or file info if no routines)
        self._save_routine_info(analysis, self._activeBlock)

    #-------------------------------------------------------------------------
    #  Specialization of NBNC main processing loop

    def _survey(self, linesToSurvey, configEntry, measurements, analysis):
        '''
        Determine how to process the survey lines based on config verb
        '''
        self.searching = False
        self.measuringRoutines = False
        writeOutput = True

        if self.VERB_MEASURE == configEntry.verb:
            self._survey_lines(linesToSurvey, [],  measurements, analysis)

        elif self.VERB_TEMPLATE_MEASURE == configEntry.verb:
            self._matchTemplateLines = True
            self._survey_lines(linesToSurvey, configEntry.paramsProcessed,
                    measurements, analysis)

        elif self.VERB_ANALYZE == configEntry.verb:
            self._survey_lines(linesToSurvey, [],  {}, analysis)
            writeOutput = bool(analysis)

        elif self.VERB_ROUTINES == configEntry.verb:
            self.measuringRoutines = True
            self._survey_lines(linesToSurvey, configEntry.paramsProcessed,
                    measurements, analysis)

        elif self.VERB_SEARCH == configEntry.verb:
            self.searching = True
            self._survey_lines(linesToSurvey, configEntry.paramsProcessed,
                    measurements, analysis)
            writeOutput = bool(analysis)

        else:
            assert False, "\nBad verb used for Code\n"
        return writeOutput

    def _alternate_line_processing(self, rawLine):
        '''
        Create a file CRC based on the raw lines
        '''
        self._fileCrc = zlib.adler32(rawLine.encode(), self._fileCrc)
        return super(Code, self)._alternate_line_processing(rawLine)

    def _measure_line(self, line, onCommentLine):
        '''
        Capture measurements for this line
        '''
        if self._measuring_block():
            if onCommentLine:
                # Filter out dead code and template lines if we're using them
                if self._matchTemplateLines and self._is_template_line(line):
                    self._log_line(line, "F", 1)
                    self.counts['TemplateLines'][self._activeBlock] += 1
                elif self._inclDeadCode and self.reDeadCode.search(line):
                    self._log_line(line, "D", 1)
                    self.counts['DeadCode'][self._activeBlock] += 1
                else:
                    self._log_line(line, "C")
                    self.counts['CommentLines'][self._activeBlock] += 1
            else:
                # Remove string literal contents to avoid false positives
                # TBD -- make this sensitive to SEARCH_STRINGS?
                strippedLine = self._strip_blanks_and_strings(line)

                # Count if inline comment, and then take out any inlines
                hasInline = False
                if self._has_inline_comment(strippedLine):
                    self.counts['AsmComments'][self._activeBlock] += 1
                    strippedLine = self._strip_inlines(strippedLine)
                    hasInline = True

                # Count as NBNC code line for this block and perform measures
                self.counts['MeasureLines'][self._activeBlock] += 1
                self._measure_line_impl(line, strippedLine)

                if self._commentsInclInline and hasInline:
                    self._log_line(line, "I", 2)
                else:
                    self._log_line(line)

        # If this isn't our active block, track totals for machine and content
        else:
            if self._activeBlock == self.MACHINE:
                self._log_line(line, "M")
                self.counts['MeasureLines'][self.MACHINE] += 1
            elif self._activeBlock == self.CONTENT:
                self._log_line(line, "+")
                self.counts['MeasureLines'][self.CONTENT] += 1

    def _analyze_line(self, line, analysis, onCommentLine):
        '''
        For routines, search, or general analysis of the line
        Processing is based on our current verb and whether the
        line is a comment or not. Only do one type of analysis.
        '''
        if not self._measuring_block():
            return

        if self.measuringRoutines and not onCommentLine:
            self._routine_analyze_impl(line, analysis)

        # There are three search modes that will cause us to or analyze a line:
        # Code only, code and comments, and comment lines only
        elif (  (onCommentLine and self._onlyComments) or
                (onCommentLine and self._includeComments) or
                (not onCommentLine and not self._onlyComments)):
            if self.searching:
                self._search_line_impl(line, analysis)
            else:
                self._analyze_line_impl(line, analysis, onCommentLine)

    def _analyze_line_impl(self, line, analysis, onCommentLine):
        '''Can be overridden to provide additional analysis'''
        pass

    #-------------------------------------------------------------------------
    #  Code measurement processing

    def _measure_line_impl(self, line, strippedLine):

        # Make CRC value from the line with whitespace reduced as a potential
        # duplicate code capture for trival changes
        self.counts['nbncCRC'][self._activeBlock] = zlib.adler32(
                line.replace('', ' ').encode(), self.counts['nbncCRC'][self._activeBlock])

        # Capture some additional per-line metrics
        self.counts['Semicolons'][self._activeBlock] += strippedLine.count(';')
        if self.reImports.search(strippedLine):
            self.counts['Imports'][self._activeBlock] += 1
            if self._logLevel: log.search(3, "import:  {}".format(line))
        if self.reClass.search(strippedLine):
            self.counts['Classes'][self._activeBlock] += 1
            if self._logLevel: log.search(2, "class:  {}".format(line))
        if self.rePreprocessor.search(strippedLine):
            self.counts['Preprocessor'][self._activeBlock] += 1
            if self._logLevel: log.search(3, "preprocessor:  {}".format(line))

        # Skip per-file routine and decision metrics if routines are being measured,
        # as these will be more accurately captured there
        if not self.measuringRoutines:

            if self.reDefaultRoutine.search(strippedLine):
                self.counts['Routines'][self._activeBlock] += 1
                if self._logLevel: log.search(2, "routine:  {}".format(line))

            decisionLine = line if self._includeStringContent else strippedLine
            if self._includeStringContent:
                decisionLine = line
            if self.reDecision.search(decisionLine):
                self.counts['Decisions'][self._activeBlock] += 1
                if self._logLevel: log.search(3, "decision:  {}".format(line))

    def _save_measures(self, measurements):
        '''
        Capture output of file measuring in measurement dictionary.

        Some measures are written for particular blocks, others are written for
        the current measure block.

        Some measures are always written, others are only added if they are positive. Some
        measures will be written as 0 if empty, others will be blank for to allow for
        pivot table counting of positives (e.g., to quickly see which files had machine code)
        '''
        mb = self._measureBlock     # Readability for measures using active block

        totalLines = sum(self.counts['TotalLines'])
        measurements[ self.LINES_TOTAL ] = totalLines

        # If raw lines is different from total, capture (i.e., line separator or ignore lines)
        rawLines = sum(self.counts['RawLines'])
        ignoreLines = sum(self.counts['SkippedLines'])
        if rawLines != totalLines:
            measurements[ self.LINES_RAW ] = rawLines
        if ignoreLines:
            measurements[ self.LINES_IGNORED ] = ignoreLines

        # For true and faux blank line totals, sum all blocks
        measurements[ self.LINES_FAUX_BLANK ] = sum(self.counts['FauxBlankLines'])
        measurements[ self.LINES_TRUE_BLANK ] = sum(self.counts['TrueBlankLines'])

        # NBNC Lines of code
        nbncLines = self.counts['MeasureLines'][mb]
        measurements[ self.LINES_CODE ] = nbncLines
        measurements[ self.CODE_FILESIZE_RANK ] = utils.match_ranking_label(
                            self.FileSizeRanks, nbncLines)

        # Machine and Content lines represent specific blocks (vs. the active block)
        machineLines = self.counts['MeasureLines'][self.MACHINE]
        if machineLines or self._writeEmptyMeasures:
            measurements[ self.LINES_MACHINE ] = machineLines if machineLines else ''
        contentLines = self.counts['MeasureLines'][self.CONTENT]
        if contentLines or self._writeEmptyMeasures:
            measurements[ self.LINES_CONTENT ] = contentLines if contentLines else ''
            measurements[ self.LINES_CODE_CONTENT ] = contentLines + nbncLines

        # Total Blank lines in block
        measurements[ self.LINES_BLANK ] = self.counts['FauxBlankLines'][mb] + self.counts['TrueBlankLines'][mb]

        # Comments and in-line comments
        commentLines = self.counts['CommentLines'][mb]
        inlineComments = self.counts['AsmComments'][mb]
        if self._commentsInclInline:
            commentLines = commentLines + inlineComments
        measurements[ self.LINES_COMMENT ] = commentLines
        if inlineComments or self._writeEmptyMeasures:
            measurements[ self.CODE_ASM_COMMENTS ] = inlineComments if inlineComments else ''

        # Cacluate comment density
        commentRatio = 0.0
        if commentLines:
            commentRatio = (nbncLines / float(commentLines))
        measurements[self.CODE_COMMENT_RANK] = utils.match_ranking_label(
                self.CommentDensityRanks, commentRatio)

        # Dead code
        deadCode = self.counts['DeadCode'][mb]
        if deadCode or self._writeEmptyMeasures:
            measurements[ self.LINES_DEADCODE ] = deadCode if deadCode else ''

        # Bytes per NBNC ratio (only for files with a majority of NBNC lines)
        fileBytes = measurements.get(basemodule.METADATA_FILESIZE, 0)
        if fileBytes > 0 and nbncLines > 0 and nbncLines > machineLines and nbncLines > contentLines:
            measurements[ self.CODE_BYTE_RATIO ] = (fileBytes / nbncLines)

        # Remaining items are written only if found, ignoring the writeEmptyMeasures flag

        semicolons = self.counts['Semicolons'][mb]
        if semicolons:
            measurements[ self.CODE_SEMICOLON ] = semicolons

        preprocessor = self.counts['Preprocessor'][mb]
        if preprocessor:
            measurements[ self.CODE_PREPROCESSOR ] = preprocessor

        templateLines = self.counts['TemplateLines'][mb]
        if templateLines:
            measurements[ self.LINES_TEMPLATE ] = templateLines

        nbncCrc = self.counts['nbncCRC'][mb]
        if nbncCrc:
            measurements[ self.CODE_CRC ] = str(nbncCrc)
        if self._fileCrc:
            measurements[ self.FILE_CRC ] = str(self._fileCrc)

        imports = self.counts['Imports'][mb]
        if imports:
            measurements[ self.CODE_IMPORTS ] = imports
            measurements[ self.CODE_IMPORT_RANK ] = utils.match_ranking_label(
                                self.ImportRanks, imports)

        decisions = self.counts['Decisions'][mb]
        if decisions:
            measurements[ self.CODE_DECISIONS ] = decisions

        routines = self.counts['Routines'][mb]
        if routines:
            measurements[ self.CODE_ROUTINES ] = routines

        classes = self.counts['Classes'][mb]
        if classes:
            measurements[ self.CODE_CLASSES ] = classes

    #-------------------------------------------------------------------------
    #  Code search processing

    def _search_line_impl(self, line, analysis):
        '''
        Delegate search functionality to searchMixin
        '''
        searchLine = line
        if not self._includeStringContent:
            searchLine = self._strip_blanks_and_strings(searchLine)

        if not self._includeComments:
            searchLine = self._strip_inlines(searchLine)

        matchTuple = self._first_match(searchLine, self._positiveSearches, self._negativeSearches)
        if matchTuple:
            origPatternStr, match = matchTuple
            searchData = {}
            searchData[ self.SEARCH_LINE    ] = line.strip()[:self.MAX_STR_LEN]
            searchData[ self.SEARCH_LINENUM ] = str(sum(self.counts['RawLines']))
            searchData[ self.SEARCH_MATCH   ] = utils.get_match_string(match).strip()[:self.MAX_STR_LEN]
            searchData[ self.SEARCH_REGEXP  ] = utils.get_match_pattern(match).strip()[:self.MAX_STR_LEN]
            searchData[ self.SEARCH_CONFIG_RE  ] = str(origPatternStr)
            analysis.append(searchData)


    #-------------------------------------------------------------------------
    #  Routine metrics processing

    def _reset_routine_counts(self):
        self.currentRoutine = {
            'Name': "SURVEYOR( File lines grouped as routine )",
            'RegEx': ("", ""),
            'Line': "",
            'LineNum': 0,
            'LineCol': 0,
            'LineIndent': 0,
            'Decisions': 0,
            'Booleans': 0,
            'Cases': 0,
            'Escapes': 0,
            'MaxIndent': 0,
            }

    def _detect_routine_start(self, line):
        '''
        Detect the start of a routine in a line using either list from config
        file with positive and negative searches, or default regex.
        '''
        if self._positiveSearches:
            # Do the negative searches first, since for many scenarios it will be faster
            return self._first_match(line, self._positiveSearches, self._negativeSearches, negativeFirst=True)
        else:
            match = self.reDefaultRoutine.search(line)
            if match:
                # Make tuple rv like _first_match
                return utils.get_match_pattern(match), match

    def _detect_indent_start(self, indentDepth):
        '''
        Detect new routine based on return to previous indent
        '''
        return ( indentDepth and
                    (self.routineIgnoreCol and indentDepth <= self.routineIgnoreCol) and
                    (indentDepth <= self.currentRoutine['LineCol']) )

    def _current_routine_ended(self, line, startMatch, indentDepth):
        '''
        Decide whether to make the current line the start of a routine based 
        on whether each routine start line is considered a seperate routine
        '''
        rv = startMatch or self._detect_indent_start(indentDepth)
        if rv and not self._routineSingleLine:
            if self._routinePrevLineStart:
                self.currentRoutine['Line'] += line
                rv = False
        self._routinePrevLineStart = rv
        return rv

    def _routine_analyze_impl(self, line, analysis):
        '''
        Identify routine begining by searching for the regular expressions provided
        in the config file. Assume the current routine ends when the next one is
        found, while collecting information on a line-by-line basis
        '''

        # Create expanded line and estimate line nesting
        expandedLine = line.expandtabs(self.routineAvgIndent)
        indentDepth = len(expandedLine) - len(expandedLine.lstrip())
        nestingApprox = int(indentDepth / self.routineAvgIndent)
        routineNest = nestingApprox - self.currentRoutine['LineIndent']

        # Strip literals and assembly comments to avoid mistaken hits
        strippedLine = self._strip_blanks_and_strings(line)
        strippedLine = self._strip_inlines(strippedLine)

        # Is this line the start of a routine?
        routineStartMatch = self._detect_routine_start(line)
        if self._current_routine_ended(line, routineStartMatch, indentDepth):
            self._save_routine_info(analysis, self._activeBlock)
            self._foundFirstRoutineSinceTransition = True
            self._reset_routine_counts()

            # Cache information about this new routine definition
            self.currentRoutine['Line'] = line
            self.currentRoutine['LineNum'] = sum(self.counts['RawLines'])
            self.currentRoutine['LineCol'] = indentDepth
            self.currentRoutine['LineIndent'] = nestingApprox
            if routineStartMatch:
                origPatternStr, match = routineStartMatch
                self.currentRoutine['Name'] = utils.get_match_string(match)
                self.currentRoutine['RegEx'] = (origPatternStr, utils.get_match_pattern(match))
                self.counts['Routines'][self._activeBlock] += 1
                if self._logLevel:
                    log.code(1, "RoutineStart({})=>  {}".format(
                                self.currentRoutine['LineNum'], self.currentRoutine['Line']))
                    log.search(3, "  re: {} => name: {}".format(
                                self.currentRoutine['RegEx'][0][:40], self.currentRoutine['Name']))
            else:
                if self._logLevel:
                    log.code(1, "RoutineEnd({})=>  {}".format(
                                self.currentRoutine['LineNum'], self.currentRoutine['Line']))

        # If there are decision matches for the line
        complexLine = line if self._includeStringContent else strippedLine
        if self.reDecision.search(complexLine):
            if self._logLevel: log.search(2, "decision: {}".format(
                    utils.get_match_string(self.reDecision.search(complexLine))))
            self.counts['Decisions'][self._activeBlock] += 1
            self.currentRoutine['Decisions'] +=1

            # Check for the maximum indentation (as an indication of nesting depth)
            if routineNest > self.currentRoutine['MaxIndent']:
                self.currentRoutine['MaxIndent'] = routineNest

        if self.reEscapes.search(complexLine):
            if self._logLevel: log.search(3, "escape: {}".format(
                    utils.get_match_string(self.reEscapes.search(complexLine))))
            self.currentRoutine['Escapes'] +=1

        if self.reCases.search(complexLine):
            if self._logLevel: log.search(3, "case: {}".format(
                    utils.get_match_string(self.reCases.search(complexLine))))
            self.currentRoutine['Cases'] +=1

        if self.reBooleans.search(complexLine):
            if self._logLevel: log.search(3, "boolean: {}".format(
                    utils.get_match_string(self.reBooleans.search(complexLine))))
            self.currentRoutine['Booleans'] +=1

    def _block_change_event(self, line, analysis, oldActiveBlock):
        '''
        Override this so routines cannot run over block boundaries
        If there are blocks of machine code or other block detection embedded in a routine
        this will lead to incorrect results
        However this is generally quite rare in code in the wild so accept the simplified 
        impelentation of assumming routines lie inside block boundaries.
        '''
        super(Code, self)._block_change_event(line, analysis, oldActiveBlock)
        if self.measuringRoutines and not self._routineSpanBlocks:
            if self._logLevel: log.code(1, "...ending routine: {}".format(self.currentRoutine['Name']))
            self._save_routine_info(analysis, oldActiveBlock)
            self._foundFirstRoutineSinceTransition = False
            self._reset_routine_counts()

    def _save_routine_info(self, analysis, activeBlock):
        '''
        Pack up the data from the last routine encountered in the measuring block
        '''
        if not self.measuringRoutines:
            return
        if not self._measuring_block(activeBlock) and not self._routineSpanBlocks:
            return

        computeMetrics = bool( self._foundFirstRoutineSinceTransition or
                                self.routineInclFileLines )

        # The NBNC length of this routine is from the start of the routine just
        # found, back to the start of the previous routine
        routineNbnc = (self.counts['MeasureLines'][activeBlock] -
                        self.totalNbncAtLastRoutine[activeBlock])
        assert routineNbnc >= 0, "Routine NBNC lines less than zero!"

        # If only found a single line, skip depending on settings, on the basis that the line
        # is a declaration or essentially empty file, which we don't want to clog up the output
        if not (routineNbnc > 1 or self._routineOutputSingle or self._writeEmptyMeasures):
            return

        measurements = {}
        routineComplexity = 0

        # Calculate complexity and provide metrics if info available
        if computeMetrics:

            # Note how many total lines to date so can subtract later
            self.totalNbncAtLastRoutine[activeBlock] = self.counts['MeasureLines'][activeBlock]

            # Escapes/return paths; assume at least one return path
            measurements[ self.ROUTINE_BRANCHINGS ] = max(1, self.currentRoutine['Escapes'])

            # Other complexity metrics
            measurements[ self.ROUTINE_DECISIONS ] = self.currentRoutine['Decisions']
            measurements[ self.ROUTINE_CASES  ] = self.currentRoutine['Cases']
            measurements[ self.ROUTINE_BOOLEANS ] = self.currentRoutine['Booleans']

            # Add up complexity depending on options
            routineComplexity += measurements[ self.ROUTINE_DECISIONS ]
            if self._complexityInclEscapes:
                routineComplexity += measurements[ self.ROUTINE_BRANCHINGS ]
            if self._complexityInclCases:
                routineComplexity += measurements[ self.ROUTINE_CASES ]
            if self._complexityInclBooleans:
                routineComplexity += measurements[ self.ROUTINE_BOOLEANS ]

        # Some values may write even if there were no routines in file; this is
        # primarily to ensure they can show up in the right order in ouput if the
        # first file of a job doesn't have any routines
        if computeMetrics or self._writeEmptyMeasures:

            # Zero out numeric values if writing due only to writeEmptyMeasures
            if not computeMetrics:
                self.currentRoutine['Name'] = 'SURVEYOR(NO MEASURE)'
                routineNbnc = 0
                routineComplexity = 0

            # NBNC lines for the routine calculated from where the last routine ended
            measurements[ self.ROUTINE_NBNC ] = routineNbnc
            measurements[ self.ROUTINE_NBNC_RANK ] = utils.match_ranking_label(
                    self.RoutineSizeRanks, routineNbnc)

            measurements[ self.ROUTINE_MAXINDENT ] = str(self.currentRoutine['MaxIndent'])
            measurements[ self.ROUTINE_MAXINDENT_RANK ] = utils.match_ranking_label(
                    self.MaxNestingRanks, self.currentRoutine['MaxIndent'])

            measurements[ self.ROUTINE_COMPLEXITY ] = routineComplexity
            measurements[ self.ROUTINE_COMPLEXITY_RANK ] = utils.match_ranking_label(
                    self.RoutineComplexityRanks, routineComplexity)

            measurements[ self.ROUTINE_NAME ] = self.currentRoutine['Name'].strip()
            measurements[ self.ROUTINE_LINE ] = self.currentRoutine['Line'].strip()
            measurements[ self.ROUTINE_LINENUM ] = str(self.currentRoutine['LineNum'])
            measurements[ self.ROUTINE_LINECOL ] = str(self.currentRoutine['LineCol'])
            measurements[ self.ROUTINE_LINEINDENT ] = str(self.currentRoutine['LineIndent'])
            measurements[ self.ROUTINE_REGEX ] = str(self.currentRoutine['RegEx'][1])[:self.MAX_STR_LEN]
            measurements[ self.ROUTINE_CONFIG_RE ] = str(self.currentRoutine['RegEx'][0])[:self.MAX_STR_LEN]

        # Capture the rest of the information
        if computeMetrics:

            # Comment values for the routine are caclulated
            # These figures are not very good, because they include method comments that
            # come before the method in the PREVIOUS routine; okay for aggregates, but
            # not good for detailed analysis of comment density in routines
            routineComments = (self.counts['CommentLines'][activeBlock] -
                                self.totalCommentsAtLastRoutine[activeBlock])
            assert routineComments >= 0, "Routine comment lines less than zero!"
            self.totalCommentsAtLastRoutine[activeBlock] = self.counts['CommentLines'][activeBlock]
            commentRatio = 0.0
            if routineComments > 0:
                commentRatio = routineNbnc / float(routineComments)
            measurements[ self.ROUTINE_COMMENTS ] = routineComments
            measurements[ self.ROUTINE_COMMENTS_RANK ] = utils.match_ranking_label(
                    self.CommentDensityRanks, commentRatio)

        if measurements:
            analysis.append(measurements)

    #-------------------------------------------------------------------------
    #  Other implementation

    def _is_template_line(self, line):
        '''
        Use regex from config file to see if line matches a template signature
        '''
        matchTuple = self._first_match(line, self._positiveSearches, self._negativeSearches)
        return bool(matchTuple)

    def _measuring_block(self, block=None):
        '''
        Some measures such as nbnc.* are desined to only be captured for
        one block -- returns whether in that block
        '''
        if block is None:
            block = self._activeBlock
        return block == self._measureBlock

    def _has_inline_comment(self, strippedLine):
        hasComment = False
        for commentStart in self.inlineCommentMatches:
            if commentStart in strippedLine:
                hasComment = True
                break
        return hasComment

    def _strip_inlines(self, strippedLine):
        '''
        Chop off ALL potential inline comments
        '''
        line = strippedLine
        for commentStart in self.inlineCommentMatches:
            if line and line[0] != '#':
                line = line.split(commentStart, 1)[0]
        return line
