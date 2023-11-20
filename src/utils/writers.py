# !/usr/bin/env python3

import os
import json
import logging
import inspect
import pathlib
from typing import TypeVar, Any
from src.utils.helpers import print_exception, path_to_str

logger = logging.getLogger(__name__)

WRITERS = {}

PathLike = TypeVar("PathLike", str, pathlib.Path, None)


def write_json(path: PathLike, data: dict):
    try:
        with open(path_to_str(path), 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=4, separators=(',', ':'))
            # json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)
    except:
        print_exception()
        logger.warning(f"Unable to read file as JSON: {path_to_str(path)}")
        return None

def write_txt(path: PathLike, data: Any):
    try:
        with open(path_to_str(path), 'w') as f:
            f.write(f)
    except:
        logger.warning(f"Unable to read file as TXT: {path_to_str(path)}")
        return None

def register_writer(file_type):
    def decorator(fn):
        WRITERS[file_type] = fn
        return fn
    return decorator

@register_writer('json')
def json_writer(path: PathLike, data: dict):
    return write_json(path, data)

@register_writer('txt')
def txt_writer(path: PathLike, data: Any):
    return write_txt(path, data)

def write(file_type):
    try:
        return WRITERS.get(file_type)
    except:
        print_exception(f"Called by {inspect.stack()[1].function}")
        return None




