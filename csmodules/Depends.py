#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    File Dependencies

    Provide results of dependencies between files, for both detailed
    analysis and aggregation with the "-g" command
'''

from code_surveyor.framework import utils
from .Code import Code


class Depends( Code ):
    '''
    Specialize Code implementaiton to focus on collecting information on
    lines that have import/include statements
    '''

    def __init__(self, options):
        super(Depends, self).__init__(options)

    @classmethod
    def _cs_config_options(cls):
        return {}

    def _survey_start(self, params):
        super(Depends, self)._survey_start(params)
        self._fileDepends = {}

    def _survey(self, linesToSurvey, configEntry, measurements, analysis):
        if self.VERB_ANALYZE == configEntry.verb:
            return super(Depends, self)._survey(linesToSurvey, configEntry, measurements, analysis)
        else:
           raise utils.CsModuleException("Dependencies csmodule is only intended to use the 'analyze' verb")

    def _analyze_line_impl(self, line, analysis, onCommentLine):
        '''
        Check for imports on each line, and record the line if found
        '''
        strippedLine = ' '.join(line.split())
        match = self.reImports.search(strippedLine)

        if match:
            lineNum = sum(self.counts['RawLines'])
            matchStr = utils.get_match_string(match)
            lineNums = self._fileDepends.get(strippedLine, [])
            lineNums.append(lineNum)
            self._fileDepends[strippedLine] = lineNums

    def _survey_end(self, measurements, analysis):
        '''
        Write out an entry for each include/import statement
        To ensure repeatability and easier readability, sort results
        '''
        depends = sorted(iter(self._fileDepends.items()), key=lambda k_v:str(k_v[0]).lower())

        for usingStatement, lineNums in depends:
            newDepends = {}
            newDepends['Depend.Using'] = usingStatement
            newDepends['Depend.Count'] = len(lineNums)
            newDepends['Depend.Files'] = { self._currentPath.fileName: [self._currentPath.folder] }
            newDepends['Depend.FileLines'] = { self._currentPath.fileName: lineNums }
            analysis.append(newDepends)


