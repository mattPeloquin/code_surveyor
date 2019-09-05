#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    Duplicate Line Detector

    Output can be considered per-file, or aggregated with the "-g" command
    to look for duplicate lines across all files in job
'''

import binascii

from code_surveyor.framework import utils
from .Code import Code


class DupeLines( Code ):
    '''
    Identifies duplicate lines in a file based on CRC
    '''
    def __init__(self, options):
        super(DupeLines, self).__init__(options)

    @classmethod
    def _cs_config_options(cls):
        return {}

    def _survey_start(self, params):
        super(DupeLines, self)._survey_start(params)

        self._linesCrc = {}

    def _survey(self, linesToSurvey, configEntry, measurements, analysis):
        if linesToSurvey:
            if self.VERB_ANALYZE == configEntry.verb:
                return super(DupeLines, self)._survey(linesToSurvey, configEntry, measurements, analysis)
            else:
                raise utils.CsModuleException("DupeLines csmodule is only intended to use the 'analyze' verb")


    def _analyze_line_impl(self, line, analysis, onCommentLine):
        '''
        Take a CRC snapshot of each line's NBNC
        '''
        lineNum = sum(self.counts['RawLines'])
        strippedLine = ' '.join(line.split())
        lineCrc = binascii.crc32(strippedLine)

        # adler32 is faster, but has too many collisions with short strings
        #lineCrc = zlib.adler32(strippedLine)

        dupeLine, lineNums = self._linesCrc.get(lineCrc, (strippedLine, []))
        #assert dupeLine == strippedLine, "CRC problem, lines should be equal:\n{}\n{}".format(dupeLine, strippedLine)

        lineNums.append(lineNum)
        self._linesCrc[lineCrc] = (dupeLine, lineNums)


    def _survey_end(self, measurements, analysis):
        '''
        Only want to capture information related to duplicate lines, so we
        do not call to our base class
        '''
        # To ensure repeatability and easier readability, sort all our dupe lines
        # by the content of the line
        dupeLines = sorted(iter(self._linesCrc.items()), key=lambda k_v:str(k_v[1][0]).lower())

        for lineCrc, (dupeLine, lineNums) in dupeLines:
            newDupes = {}

            # These measures can be useful for general analysis
            newDupes['DupeLine.CRC'] = lineCrc
            newDupes['DupeLine.Count'] = len(lineNums)
            newDupes['DupeLine.Content'] = dupeLine

            # These metrics are really only interesting for aggregate analysis
            newDupes['DupeLine.Files'] = { self._currentPath.fileName: [self._currentPath.folder] }
            newDupes['DupeLine.FileLines'] = { self._currentPath.fileName: lineNums }
            newDupes['DupeLine.FileLineCount'] = { self._currentPath.fileName: len(lineNums) }

            analysis.append(newDupes)
