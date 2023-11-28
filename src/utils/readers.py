#!/usr/bin/env python3

import os
import csv
import json
import inspect
import logging
import pathlib
from typing import TypeVar
import subprocess as sp
import xml.etree.ElementTree as ET
from tifffile import TiffFile
from src.utils.helpers import print_exception, path_to_str


logger = logging.getLogger(__name__)

READERS = {}

PathLike = TypeVar("PathLike", str, pathlib.Path, None)


def read_txt(path: PathLike):
    try:
        with open(path_to_str(path), mode='r') as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Unable to read file as TXT: {path_to_str(path)}. Reason: {e.__class__.__name__}")
        return None

def read_csv(path: PathLike):
    try:
        with open(path_to_str(path), mode='r') as f:
            return list(csv.reader(f))
    except Exception as e:
        logger.warning(f"Unable to read file as HTML: {path_to_str(path)}. Reason: {e.__class__.__name__}")
        return None

def read_html(path: PathLike):
    try:
        with open(path_to_str(path), mode='r') as f:
            data = f.read()
            return data
    except Exception as e:
        logger.warning(f"Unable to read file as HTML: {path_to_str(path)}. Reason: {e.__class__.__name__}")
        return None

def read_json(path: PathLike):
    # with open(file_path, mode='r') as f:
    #     return json.load(f)
    try:
        with open(path_to_str(path), mode='r') as f:
            data = json.load(f)
            if type(data) == bytes:
                logger.warning(f'Decoding byte data of {path}')
                data = data.decode()
            return data
    except Exception as e:
        logger.warning(f"Unable to read file as JSON: {path_to_str(path)}. Reason: {e.__class__.__name__}")
        return None

def read_xml(path: PathLike):
    try:
        tree = ET.parse(path_to_str(path))
        root = tree.getroot()
        return root
    except Exception as e:
        logger.warning(f"Unable to read XML: {path_to_str(path)}. Reason: {e.__class__.__name__}")


def read_tiffinfo(path: PathLike):
    o = sp.check_output(['tiffinfo', path_to_str(path)], universal_newlines=True, errors='ignore')
    print(o)
    return o
    # return o.decode()


def read_tifftags(path: PathLike):
    page = TiffFile(path_to_str(path)).pages[0] # first page only
    tags = page.tags.values()
    data = {}
    for t in tags:
        unknown = 0
        if t.name:
            name = t.name
            data[name] = {}
        else:
            name = f"tag-{unknown}"
        data[name] = {}
        print(f'TIFF tag found: {name}')
        if t.code:
            data[name]['code'] = t.code
        if t.count:
            data[name]['count'] = t.count
        if t.dtype:
            data[name]['dtype'] = t.dtype
        if t.value:
            data[name]['value'] = t.value
    return data  # len = 10 for test image

def register_reader(file_type):
    def decorator(fn):
        READERS[file_type] = fn
        return fn
    return decorator


@register_reader('txt')
def txt_reader(path: PathLike):
    return read_txt(path)

@register_reader('csv')
def csv_reader(path: PathLike):
    return read_csv(path)


@register_reader('html')
def html_reader(path: PathLike):
    return read_html(path)

@register_reader('json')
def json_reader(path: PathLike):
    return read_json(path)

@register_reader('xml')
def xml_reader(path: PathLike):
    return read_xml(path)

@register_reader('tifftags')
def tifftags_reader(path: PathLike):
    return read_tifftags(path)

@register_reader('tiffinfo')
def tiffinfo_reader(path: PathLike):
    return read_tiffinfo(path)

def read(file_type):
    try:
        return READERS.get(file_type)
    except:
        print_exception(f"[{inspect.stack()[1].function}]")
        return None


'''

VolumeJosef tags
<tifffile.TiffTag 256 ImageWidth @16777226>,
 <tifffile.TiffTag 257 ImageLength @16777238>,
 <tifffile.TiffTag 258 BitsPerSample @16777250>,
 <tifffile.TiffTag 262 PhotometricInterpretation @16777262>,
 <tifffile.TiffTag 273 StripOffsets @16777274>,
 <tifffile.TiffTag 277 SamplesPerPixel @16777286>,
 <tifffile.TiffTag 279 StripByteCounts @16777298>]


'''