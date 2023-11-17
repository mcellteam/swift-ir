#!/usr/bin/env python3

'''This class validates alignment data.'''

import os
import json
import inspect
import pathlib
from typing import TypeVar, Any
from src.models.data import DataModel
from src.utils.helpers import print_exception

__all__ = ['Validator']

PathLike = TypeVar("PathLike", str, pathlib.Path, None)



class Validator:
    VALIDATORS = {}

    def __init__(self, dm: DataModel):
        self.dm = dm

    def validate_example(self, index: int):
        print(f"Running example validation test, index={index}...")


    def register_validator(self, test_type):
        def decorator(fn):
            self.VALIDATORS[test_type] = fn
            return fn
        return decorator


    @register_validator('example')
    def example_validator(self, index: int):
        return self.validate_example(index)


    def validate(self, test_type):
        return self.VALIDATORS.get(test_type)