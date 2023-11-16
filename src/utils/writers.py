# !/usr/bin/env python3

import json
import os
import pathlib
from typing import TypeVar, Any

WRITERS = {}

PathLike = TypeVar("PathLike", str, pathlib.Path, None)


def write_json(path: PathLike, data: dict):
    with open(path, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=4, separators=(',', ':'))
        # json.JSONEncoder(indent=2, separators=(",", ": "), sort_keys=True)

def write_txt(path: PathLike, data: Any):
    with open(path, 'w') as f:
        f.write(str(data))

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
    return WRITERS.get(file_type)