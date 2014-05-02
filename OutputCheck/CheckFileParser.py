import collections
import logging
import pprint
import re
from .Utils import isA
# Cannot import Directives here due to circular dependencies

_logger = logging.getLogger(__name__)

class FileLocation(object):
    def __init__(self, fileName, lineNumber):
        self.fileName = fileName
        self.lineNumber = lineNumber

    def __str__(self):
        return self.fileName + ':' + str(self.lineNumber)

class ParsingException(Exception):
    def __init__(self, msg):   
        super(self.__class__,self).__init__(msg)

    def __str__(self):
        return str(self.__class__.__name__) + ": " + self.args[0]

class CheckFileParser:
    def  __init__(self, checkPrefix, lineCommentPrefix):
        self.checkPrefix = checkPrefix
        self.lineCommentPrefix = lineCommentPrefix

        # Find directives
        import inspect
        directivePrefix = r'^\s*' + self.lineCommentPrefix + r'\s*' + self.checkPrefix
        patternRegex = r'(.+)$'
        directive = collections.namedtuple('Directive',['Regex','Class'])
        
        directives = []

        # Try to find Directives dynamically
        from . import Directives
        for (name,object) in Directives.__dict__.items():
            if not inspect.isclass(object):
                continue

            if getattr(object,'directiveToken',None) != None:
                # Found a match
                directives.append( directive( Regex=re.compile(directivePrefix + 
                                                               object.directiveToken() + 
                                                               '\s*' + # Ignore all whitespace after directive
                                                               patternRegex),
                                              Class=object
                                            ) 
                                 )

        self.directives = directives
        _logger.debug('Found directives:\n{}'.format(pprint.pformat(self.directives)))

    def parse(self, checkFile):
        from . import Directives
        directiveObjects = []

        lineNumber=1
        location = None
        for line in checkFile.readlines():
            for d in self.directives:
                m = d.Regex.match(line)
                if m != None:
                    location = FileLocation(checkFile.name, lineNumber)

                    if ( len(directiveObjects) > 0 and 
                         isinstance(directiveObjects[-1], Directives.CheckNot) and 
                         d.Class == Directives.CheckNot
                       ):
                        # Do not allow consecutive CHECK-NOT directives, just add
                        # pattern to previous CHECK-NOT
                        directiveObjects[-1].addPattern(m.group(1), location)
                        _logger.debug('{file}:{line} : Added pattern {pattern} to directive\n{directive}'.format(file=checkFile.name,
                                                                                                                  line=lineNumber,
                                                                                                                  pattern=m.group(1),
                                                                                                                  directive=directiveObjects[-1]))
                    else:
                        # Create new Directive Object with a pattern (as string)
                        directiveObjects.append( d.Class(m.group(1), location) )
                        _logger.debug('{file}:{line} : Creating directive\n{directive}'.format(file=checkFile.name, line=lineNumber, directive=directiveObjects[-1]))

            lineNumber += 1

        self._validateDirectives(directiveObjects, checkFile.name)
        return directiveObjects

    def _validateDirectives(self, directiveList, checkFileName):

        if len(directiveList) == 0:
            raise ParsingException("'{file}' does not contain any CHECK directives".format(file=checkFileName))

        from . import Directives
        """
            We should enforce that every CHECK-NEXT directive in the list (apart from if it
            is the first directive) should have a CHECK or CHECK-NEXT before it.

            * CHECK-NEXT is the first directive
            * CHECK-NEXT either has one of the following directives before it CHECK, CHECK-NEXT or CHECK-L

        """
        supportedDirectives = [Directives.CheckNext, Directives.Check, Directives.CheckLiteral]
        for (index,directive) in enumerate(directiveList):
            if isinstance(directive, Directives.CheckNext):
                if index > 0:
                    before = directiveList[index -1]

                    if not isA(before, supportedDirectives):
                        requiredTypes = " or ".join( [ "CHECK{suffix}".format(suffix=d.directiveToken()) for d in supportedDirectives])
                        raise ParsingException("{directive} must have a {requiredTypes} directive before it instead of a {bad}".format(
                                                  directive=directive,
                                                  requiredTypes=requiredTypes,
                                                  check=Directives.Check.directiveToken(),
                                                  checkNext=Directives.CheckNext.directiveToken(),
                                                  bad=before)
                                              )

        """
            We should enforce for every CHECK-NOT directive that the next directive (if it exists) is
            a CHECK or CHECK-L directive
        """
        last = len(directiveList) -1
        supportedDirectives = [ Directives.Check, Directives.CheckLiteral ]
        for (index,directive) in enumerate(directiveList):
            if isinstance(directive, Directives.CheckNot):
                if index < last:
                    after = directiveList[index +1]
                    if not isA(after, supportedDirectives):
                        requiredTypes = " or ".join( [ "CHECK{suffix}".format(suffix=d.directiveToken()) for d in supportedDirectives])
                        raise ParsingException("{directive} must have a {requiredTypes} directive after it instead of a {bad}".format(
                                                  directive=directive,
                                                  requiredTypes=requiredTypes,
                                                  check=Directives.Check.directiveToken(),
                                                  bad=after)
                                              )
