#---- Code Surveyor, Copyright 2019 Matt Peloquin, MIT License
'''
    Ecapsulates Management of Surveyor measurement modules
'''

from . import uistrings
from . import utils
from . import log


class CodeSurveyorModules( object ):
    '''
    Manages csmodules for the ConfigStack
    Note the "csmodules" are actually instances of the class inside each python
    module. The modules are loaded lazily and the classes are cached.
    Since csmodule classes may have different initialization states set by
    options, we include the option strings as part of the cache name.
    '''
    PACKAGE_PREFIX = 'csmodules.'
    RequiredMethods = [ 'open_file', 'process_file',
            'match_measure', 'can_do_verb', 'can_do_measure',
            'add_param', 'verb_end_marker']

    def __init__(self):
        self.moduleList = {}

    def get_csmodule(self, moduleName, options=[]):
        '''
        Return the csmodule class with the given name, if it exists
        '''
        modHash = self._csmod_hash(moduleName, options)
        module = self.moduleList.get(modHash)
        if not module:
            log.config(2, "Loading csmodule: {}".format(moduleName))
            module = self._load_csmodule(moduleName, options)
            self.moduleList[modHash] = module
        return module

    def _csmod_hash(self, moduleName, options):
        if options is None:
            return moduleName
        else:
            optHash = ""
            for name, value in options:
                if value is None:
                    optHash += name
                else:
                    optHash += name + str(value)
            return moduleName + optHash

    def _load_csmodule(self, modName, options):
        '''
        Import a module given its name, and return the object.
        If there are any problems finding or loading the module we return None.
        If the module has python errors in it we treat as catastrophic
        failure and allow caller to handle.
        '''
        csmoduleClassInstance = None
        try:
            # Load the module called modName, and then get class inside the
            # module with the same name
            moduleFile = __import__(self.PACKAGE_PREFIX + modName)
            module = getattr(moduleFile, modName)
            moduleClass = getattr(module, modName)

            # Instantiate the module
            csmoduleClassInstance = moduleClass(options)

            # Make sure required methods are in the class; fatal error if not
            for method in self.RequiredMethods:
                getattr(csmoduleClassInstance, method)

        except (ImportError, AttributeError):
            log.traceback()
            raise utils.SurveyorException(uistrings.STR_ErrorLoadingModule.format(modName))
        return csmoduleClassInstance

