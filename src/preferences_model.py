#!/usr/bin/env python3

import inspect
import logging
from copy import deepcopy

try:
    import src.config as cfg
except:
    pass

__all__ = ['PreferencesModel']

logger = logging.getLogger(__name__)


class PreferencesModel:
    """ Encapsulate datamodel dictionary and wrap with methods for convenience """

    def __init__(self):
        logger.info('')

        logger.info('<<')

    def __setitem__(self, key, item):
        self._data[key] = item

    def __getitem__(self, key):
        return self._data[key]

    def __repr__(self):
        return self.to_json()

    def __str__(self):
        return self.dest() + '.swiftir'

    def __copy__(self):
        logger.info('Creating __copy__ of DataModel...')
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        return result

    def __deepcopy__(self, memo):
        caller = inspect.stack()[1].function
        logger.info(f'Creating __deepcopy__ of DataModel [{caller}]...')
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    def load(self):
        pass