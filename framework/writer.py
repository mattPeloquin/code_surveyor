#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Write the output of Surveyor measures
    Supports various output formats and the creation of multiple files
    based on the config file "OUT:" tag
'''

import os
import sys
import csv
import shutil
import string
import errno
from base64 import b64encode
from xml.dom import minidom

from code_surveyor.framework import log  # No relative path to share module globals
from . import configentry
from . import uistrings
from . import utils


def get_writer(typeStr, status_callback, outDir, outputFile, ignoreMetaOutfiles, itemColOrder=[]):
    '''
    Factory method for writer variations
    '''
    writer = None
    if typeStr == 'xml':
        writer = Xml(status_callback, outDir, outputFile, ignoreMetaOutfiles)
    else:
        writer = Delimited(typeStr, status_callback, outDir, outputFile, ignoreMetaOutfiles, itemColOrder)
    return writer


class MeasureWriter( object ):
    '''
    Base class for writing Surveyor measurement output, which creates
    one row for each measure with name-values in columns.
    A default output file (or stream) can be used, as well as output files
    created by using the "OUT:" tag in surveyor config files.
    Output files are opened lazily in the location of the default output.
    '''
    def __init__(self, status_callback, outDir, outputFile, ignoreMetaOutfiles):

        # The folder where output files will be placed (there can only be one)
        self._outDir = outDir

        # Keep track of all the output files opened
        self._outputFiles = {}

        # Store away the default output filename to use if
        # output file names are not defined in config tages
        self._defFileName = outputFile

        # If a file extension is not specified for the output file, writer
        # specializations can add one
        self._defFileExt = None

        # Special case stdout output
        if self._defFileName is None:
            self._defFileName = 'stdout'
            self._outputFiles[self._defFileName] = sys.stdout

        # Ignore output files based on config tag meta data
        self._ignoreMetaOutfiles = ignoreMetaOutfiles

        # For UI status updates; provides feedback on files opended
        self._status_callback = status_callback

    def using_console(self):
        return self._defFileName == 'stdout'

    def close_files(self):
        for fileName in list(self._outputFiles.keys()):
            self._close(fileName, self._outputFiles[fileName])
            del self._outputFiles[fileName]

    #-------------------------------------------------------------------------
    # Specialize writer behavior through these methods

    def write_items(self, measures, analysisResults):
        raise utils.AbstractMethod(self)

    def _open_file(self, fileName):
        self._status_callback(uistrings.STR_OpenedOutput.format(
                os.path.abspath(os.path.join(self._outDir,fileName))))

    def _close_file(self, fileName):
        raise utils.AbstractMethod(self)

    def _fixup_column_headers(self, filename):
        pass

    #-------------------------------------------------------------------------

    def _close(self, fileName, openFile):
        if (openFile is not None) and (sys.stdout is not openFile):
            self._close_file(fileName)

    def _get_output_file(self, measures):
        '''
        Lookup file name based on measures then retrieve file from cache or
        open if it hasn't been cached yet
        '''
        isNewFile = False
        fileName = ''
        try:
            if self.using_console():
                fileName = self._defFileName
            else:
                fileName = self._get_output_filename(measures)
                if fileName not in self._outputFiles:
                    self._outputFiles[fileName] = self._open_file(fileName)
                    isNewFile = True
        except IOError as e:
            if e.errno == errno.EACCES:
                raise utils.OutputException(uistrings.STR_ErrorOpeningOutputAccess.format(fileName))
            else:
                raise utils.OutputException(uistrings.STR_ErrorOpeningOutput.format(fileName, str(e)))
        return self._outputFiles[fileName], fileName, isNewFile

    def _get_output_filename(self, measures):
        '''
        Check whether any tags in the metadata are requesting output
        be redirected to a different output file; otherwise use default
        '''
        outFileName = self._defFileName

        # Only try to open a new file if using output path
        if not self._ignoreMetaOutfiles:
            for itemName, itemValue in measures.items():
                if configentry.is_tag_name(itemName):
                    fileName = configentry.filename_from_tag(itemValue)
                    if fileName is not None:
                        outFileName = fileName
                        # Don't want out file name in output
                        del measures[itemName]
                        break

        # If there is no extension on the file name, give it one from our type
        fileName, fileExt = os.path.splitext(outFileName)
        if self._defFileExt and not fileExt:
            outFileName = outFileName + '.' + self._defFileExt

        return outFileName


class Delimited( MeasureWriter ):
    '''
    Writes delimited measure output to a file or stream, which is the
    main Surveyor use case.
    '''
    def __init__(self, delimiter, status_callback, outDir, outputFile,
                ignoreMetaOutfiles, itemColOrder ):
        super(Delimited, self).__init__(status_callback, outDir, outputFile, 
                                            ignoreMetaOutfiles)
        self._csvWriter = None
        self._delimiter = delimiter
        self._rawFiles = {}

        # The delimiter may not be a comma, but most programs will
        # figure that out from a csv extension, so we don't bother changing
        self._defFileExt = "csv"

        # For each output file it is possible to have the measure columns
        # change over the course of the job, since it isn't possible to know 
        # what measures might requested by nested config files.
        # Use this dictionary to track the measures for each file on a first-come, 
        # first-serve basis. Once a measure shows up in a job, store its name as a key,
        # and it's column, to use that column to write values in the future.
        self._colMeasureTracker = {}

        # For each output file need to track whether the heading row has been appended to.
        # If it has, rewrite the column headers at the end of the job
        self._colMeasureIsDirty = {}

        # Stash any item Names to place in a particular column order
        self._itemColOrder = itemColOrder

        # Spcecial case console output
        if self.using_console():
            self._colMeasureTracker[self._defFileName] = {}
            self._colMeasureIsDirty[self._defFileName] = False

    def write_items(self, measures, analysisResults):
        '''
        Write delimited lines based on measures and analysisResults
        There is one set of row items in measures, and zero or more sets of
        row items in analysisResults.
        Create at least one row based on measures; if there are analysisResults,
        combine the measures into a row for each analysisResult.
        '''
        outputFile, fileName, isNewFile = self._get_output_file(measures)

        # If analysis results, create a measurement row for each analysis item 
        # that includes both the measures and the analysis
        outputRows = []
        if analysisResults:
            for result in analysisResults:
                outputRowDict = dict(measures)
                outputRowDict.update(result)
                outputRows.append(outputRowDict)
        else:
            outputRows.append(dict(measures))

        # Write heading row for new files
        # Although it may be rewritten if the col names change during the course
        # of a job, optimize for the case where the columns won't change
        # and create a column heading string based on names in the first row.
        if isNewFile:
            self._populate_col_tracker(outputRows[0], fileName)
            outputFile.writerow(self._col_create_names_from_keys(fileName))

        # Write rows
        for row in outputRows:
            outputFile.writerow(self._col_output_list(row, fileName))

    def _get_output_file(self, measures):
        outputFile, fileName, isNew = MeasureWriter._get_output_file(self, measures)
        if isNew:
            self._colMeasureTracker[fileName] = {}
            self._colMeasureIsDirty[fileName] = False
        return outputFile, fileName, isNew

    def _open_file(self, fileName):
        MeasureWriter._open_file(self, fileName)
        filePath = os.path.join(self._outDir, fileName)
        self._rawFiles[fileName] = open(filePath, 'w', encoding='utf-8', newline='')
        outWriter = csv.writer( self._rawFiles[fileName], delimiter=self._delimiter, 
                                quoting=csv.QUOTE_NONNUMERIC)
        log.file(2, "Opened Delimited Output File: {}".format(filePath))
        return outWriter

    def _close_file(self, fileName):
        self._rawFiles[fileName].close()
        if self._colMeasureIsDirty[fileName]:
            self._fixup_column_headers(fileName)

    #-----------------------------------------------------------------------------
    #  Column methods

    def _populate_col_tracker(self, firstRow, outFilename):
        '''
        Sets up the writer to output columns in a particular order by populating
        our column index dictionary once at the start of each file using
        the first row items and an order list if provided
        '''
        itemNames = [itemName for itemName, _itemValue in firstRow.items()]

        # Split itemNames into two lists of anything that is in our predefined
        # order list, and anything that is not
        orderedNames = []
        unorderedNames = []
        for itemName in itemNames:
            if itemName in self._itemColOrder:
                orderedNames.append(itemName)
            else:
                unorderedNames.append(itemName)

        # Put orderedNames in the order defined by the itemOrder list, sort the rest,
        # and then add them to our column dictionary
        orderedNames = [itemName for itemName in self._itemColOrder if itemName in orderedNames]
        unorderedNames.sort()

        # The outputFileCols dictionary is modified in place
        outputFileCols = self._colMeasureTracker[outFilename]
        for itemName in list(orderedNames + unorderedNames):
            listPos = len(outputFileCols)
            outputFileCols[itemName] = listPos

    def _col_output_list(self, outputItems, outFilename):
        '''
        Given a set of Surveyor output data, package it into a row
        that has name-value pairs for all measures.
        Align each name-value pair based on existing columns created for outFilename,
        and add any new ones at then end.
        '''
        # Create dict of output values, keyed on the linear position of the
        # item in previous writing of this file (in self._colMeasureTracker)
        # If a column hasn't been encountered add it at the end
        outputColValue = {}
        outputFileCols = self._colMeasureTracker[outFilename]
        for itemName, itemValue in outputItems.items():
            listPos = None
            try:
                listPos = outputFileCols[itemName]
            except KeyError:
                listPos = len(outputFileCols)
                outputFileCols[itemName] = listPos
                self._colMeasureIsDirty[outFilename] = True

            outputColValue[listPos] = utils.safe_string(itemValue)

        # Create return list, padding any col values that don't exist
        outputValues = []
        for colNum in range(0, len(outputFileCols)):
            try:
                outputValues.append(outputColValue[colNum])
            except KeyError:
                outputValues.append('')
        return outputValues

    def _col_create_names_from_keys(self, filename):
        '''
        The dictionary of columns is keyed on names and has the
        column position for value
        '''
        outColNames = [''] * len(self._colMeasureTracker[filename])
        for (colNameKey, colPosValue) in self._colMeasureTracker[filename].items():
            outColNames[colPosValue] = colNameKey
        return outColNames

    def _fixup_column_headers(self, filename):
        '''
        If any columns were added to a file in the middle of the job run this after
        file is closed to make sure the first row column names are matched up.
        This is the only way to ensure the file has the correct information;
        which is unfortunate due to the potential expense of this operation.
        '''
        # Create random file temp file in the same place as the outfile
        randomLetters = b64encode( os.urandom(16) ).decode('utf-8')
        ValidChars = string.ascii_letters + string.digits
        randomLetters = ''.join([c for c in randomLetters if (c in ValidChars)])
        tmpFileName = "_surveyor_tmp{}_{}".format(randomLetters, filename)
        tempPath = os.path.join(self._outDir, tmpFileName )

        log.msg(1, "Fixing output headers: {} ==> {}".format(tmpFileName, filename))
        with open(tempPath, 'w', encoding='utf-8') as tempFile:
            # Write new header line
            tempFile.write(self._delimiter.join(
                            self._col_create_names_from_keys(filename)) + '\n')
            # Move lines from original file to new, skipping header line
            oldPath = os.path.join(self._outDir, filename)
            with open(oldPath, 'r', encoding='utf-8') as oldFile:
                _header_line = oldFile.readline()
                for line in oldFile:
                    tempFile.write(line)

        shutil.move(tempPath, oldPath)


class Xml( MeasureWriter ):
    '''
    Writes an XML file where each node is a file. Per-file measures are
    inlcuded as attributes of the node, while analysis items are added
    as child nodes called item.
    '''

    def __init__(self, status_callback, outDir, outputFile, ignoreMetaOutfiles):
        super(Xml, self).__init__(status_callback, outDir, outputFile, ignoreMetaOutfiles)
        self._defFileExt = "xml"

    def write_items(self, measures, analysisResults):
        outputFile, fileName, isNewFile = self._get_output_file(measures)

        # Create the file element
        fileNode = minidom.Element("file")
        for itemName, itemValue in measures.items():
            fileNode.setAttribute(itemName, utils.safe_string(itemValue))

        # Create unique analysisResults entries
        itemNum = 1
        for item in analysisResults:
            itemNode = minidom.Element("item" + str(itemNum))
            for itemName, itemValue in item.items():
                itemNode.setAttribute(itemName, utils.safe_string(itemValue))
            itemNum += 1
            fileNode.appendChild(itemNode)

        outputFile.write(fileNode.toprettyxml(indent="  "))

    def _open_file(self, filename):
        MeasureWriter._open_file(self, filename)
        filePath = os.path.join(self._outDir, filename)
        outFile = open(filePath, 'w', encoding='utf-8')
        doc = minidom.Document()
        outFile.write(doc.toprettyxml())
        log.file(2, "Opened XML Output File: {}".format(filePath))
        return outFile

    def _close_file(self, fileName):
        self._outputFiles[fileName].close()
