#---- Code Surveyor, Copyright 2020 Matt Peloquin, MIT License
'''
    Web Module -- Used to separate code from content/layout in web
    or similar file types.
'''

import re
from .Code import Code

class Web( Code ):
    '''
    Adds a new block type called "content"
    Extends Code module by using the block detection mechanism to separate
    script/code blocks from content blocks
    Records the content metrics

    See NBNC.py and Machine.py for description of block detection.
    '''

    ConfigOptions_Web = {
        'SCRIPT_ADD_DETECT': ('''self.blockDetectors[self._measureBlock].append(eval(optValue))''',
            'Adds a script detection regex'),
        'SCRIPT_DETECTORS': ('''self.blockDetectors[self._measureBlock] = eval(optValue)''',
            'Completely replaces script detection regexs'),
        }

    def __init__(self, options):
        super(Web, self).__init__(options)

    @classmethod
    def _cs_config_options(cls):
        return cls.ConfigOptions_Web

    def _cs_init_config_options(self):
        super(Web, self)._cs_init_config_options()
        self._configOptionDict.update(self.ConfigOptions_Web)

        # Override default measurement block to measure what is inside block detection -
        # anything outside block detection (position 0) is now "content"
        self.CONTENT = 0
        self.HUMAN_CODE = 2
        self._measureBlock = self.HUMAN_CODE

        # Add block detections for web script
        # The set of items below should work well for common web file types
        self.blockDetectors[self._measureBlock] = [
            # Common script tags
            [   re.compile( r"[<{]%", self._reFlags),
                re.compile( r"%[>}]", self._reFlags),
                ],
            [   re.compile( r"<script", self._reFlags),
                re.compile( r"</script>", self._reFlags),
                ],
        ]


    def _log_block_level(self):
        # Log all lines (not just code/content) at Debug level 3
        return 3



