#!/usr/bin/env python3

import os
import csv
import json
import logging
import pathlib
from typing import TypeVar
import subprocess as sp
import xml.etree.ElementTree as ET
from tifffile import TiffFile
import src.config as cfg

logger = logging.getLogger(__name__)

PARSERS = {}

PathLike = TypeVar("PathLike", str, pathlib.Path, None)

def parse_csv(path: PathLike):
    with open(path, mode='r') as f:
        reader = csv.reader(f)
        return list(reader)

def parse_json(path: PathLike):
    with open(path, mode='r') as f:
        return json.load(f)

def parse_xml(path: PathLike):
    tree = ET.parse(path)
    root = tree.getroot()
    return root

def parse_tifftags(path: PathLike):
    page = TiffFile(path).pages[0] # first page only
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

def parse_tiffinfo(path: PathLike):
    o = sp.check_output(['tiffinfo', path])
    return o.decode()

def register_parser(file_type):
    def decorator(fn):
        PARSERS[file_type] = fn
        return fn
    return decorator

@register_parser('csv')
def csv_parser(path: PathLike):
    return parse_csv(path)

@register_parser('json')
def json_parser(path: PathLike):
    return parse_json(path)

@register_parser('xml')
def xml_parser(path: PathLike):
    return parse_xml(path)

@register_parser('tifftags')
def tifftags_parser(path: PathLike):
    return parse_tifftags(path)

@register_parser('tiffinfo')
def tiffinfo_parser(path: PathLike):
    return parse_tiffinfo(path)

def parse(file_type):
    return PARSERS.get(file_type)



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