def isA(instance, typeList):
    """
        Return true if ``instance`` is an instance of any the Directive
        types in ``typeList``
    """
    return any([isinstance(instance,iType) for iType in typeList])
