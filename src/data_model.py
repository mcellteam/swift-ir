#!/usr/bin/env python3

"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""
import os
import re
import sys
import copy
import json
import uuid
import inspect
import logging
import hashlib
import time
import pprint
import platform
import statistics
from typing import Dict, Any
from glob import glob
from copy import deepcopy
from heapq import nsmallest
from operator import itemgetter
from datetime import datetime
from dataclasses import dataclass
from functools import cache, cached_property
from functools import reduce
import numpy as np
import zarr
from qtpy.QtCore import QObject, Signal, Slot, QMutex
from qtpy.QtWidgets import QApplication

from src.funcs_image import SetStackCafm
from src.hash_table import HashTable
from src.helpers import print_exception, caller_name
from src.funcs_image import ComputeBoundingRect, ImageSize
# from src.hash_table import HashTable
try:
    import src.config as cfg
except:
    pass

__all__ = ['DataModel']

logger = logging.getLogger(__name__)

class ScaleIterator:
    def __init__(self, data):
        self._data = data
        self._index = 0

    def __next__(self):
        if self._index < len(self._data):
            result =  self._data[self._index]
        else:
            raise StopIteration
        self._index += 1
        return result

    def __iter__(self):
        return self


class Scale:
    pass

def date_time():
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

class Signals(QObject):
    zposChanged = Signal()
    dataChanged = Signal()
    outputSettingsChanged = Signal()
    swimSettingsChanged = Signal()


class DataModel:

    """ Encapsulate datamodel dictionary and wrap with methods for convenience """
    def __init__(self, data=None, data_location=None, series_location=None, read_only=False, initialize=False, series_info=None):
        self._current_version = cfg.VERSION
        if data:
            self._data = data  # Load project data from file
        elif initialize:
            try:
                series_info
            except NameError:
                logger.warning(f"'series_info' argument is needed to initialize data model."); return
            try:
                data_location
            except NameError:
                logger.warning(f"'data_location' argument is needed to initialize data model."); return
            self._data = {}
            self.initializeStack(series_info=series_info, series_location=series_location, data_location=data_location)
        if not read_only:
            if series_location:
                self.series_location = series_location
            self.ht = None
            self._data['modified'] = date_time()
            self.signals = Signals()
            self.signals.dataChanged.connect(lambda: logger.critical('emission!'))

    def loadHashTable(self):
        logger.info('')
        self.ht = cfg.ht = HashTable(self)

    def __iter__(self):
        for item in self['stack'][self.zpos]['levels'][self.level]:
            yield item

    def __call__(self):
        return self['stack']

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

    def __len__(self):
        try:
            return self['series']['count']
        except:
            logger.warning('No Images Found')

    @property
    def zattrs(self):
        s = self.level
        path = os.path.join(self.data_location, 'zarr', s)
        z = zarr.open(path)
        return z.attrs

    @property
    def zarr(self):
        s = self.level
        path = os.path.join(self.data_location, 'zarr', s)
        z = zarr.open(path)
        return z


    def to_file(self):
        path = os.path.join(self.dest(), 'state_' + date_time() + '.swiftir')
        with open(path, 'w') as f:
            f.write(str(self.to_json()))

    @property
    def count(self):
        return len(self)

    @property
    def basename(self) -> str:
        '''Get transforming image path.'''
        return self['stack'][self.zpos]['levels'][self.level]['swim_settings']['name']

    @property
    def refname(self) -> str:
        '''Get reference image path.'''
        return self['stack'][self.zpos]['levels'][self.level]['swim_settings']['reference_name']

    @property
    def created(self):
        '''Get time stamp, created.'''
        return self._data['created']

    @created.setter
    def created(self, val):
        '''Set time stamp, created.'''
        self._data['created'] = val

    @property
    def modified(self):
        '''Get time stamp, modified.'''
        return self['modified']

    @modified.setter
    def modified(self, val):
        '''Set time stamp, modified.'''
        self['modified'] = val

    @property
    def series_location(self):
        '''Set alignment data series_location.'''
        return self['info']['series_location']

    @series_location.setter
    def series_location(self, p):
        '''Get alignment data series_location.'''
        self['info']['series_location'] = p

    @property
    def data_location(self):
        '''Set alignment data series_location.'''
        return self['info']['data_location']

    @data_location.setter
    def data_location(self, p):
        '''Get alignment data series_location.'''
        self['info']['data_location'] = p

    def dest(self) -> str:
        return self['info']['data_location']

    @property
    def scales(self) -> list[str]:
        '''Get scale levels list.'''
        return natural_sort(self['series']['levels'])

    @property
    def levels(self) -> list[str]:
        '''Get scale levels list.'''
        return natural_sort(self['series']['levels'])

    @property
    def source_path(self):
        '''Get source path.'''
        return self['source_path']

    @source_path.setter
    def source_path(self, p):
        '''Set source path.'''
        self['source_path'] = p

    @property
    def last_opened(self):
        '''Get last opened time stamp.'''
        return self['modified']

    @last_opened.setter
    def last_opened(self, val):
        '''Set last opened time stamp.'''
        self['modified'] = val

    @property
    def zpos(self):
        '''Get global Z-position.'''
        return self['current']['z_position']

    @zpos.setter
    def zpos(self, index):
        '''Set global Z-position. Signals UI to update.'''
        caller = inspect.stack()[1].function
        # self['data']['Current Section (Index)'] = index
        if int(index) in range(0, len(self)):
            if int(index) != self.zpos:
                self['current']['z_position'] = int(index)
                logger.info(f"[{index}] Z-position Changed!")
                self.signals.zposChanged.emit()
                QApplication.processEvents()
        else:
            logger.warning(f'\nINDEX OUT OF RANGE: {index} [caller: {inspect.stack()[1].function}]\n')

    @property
    def cname(self) -> str:
        '''Get compression type'''
        return self['series']['cname']

    @cname.setter
    def cname(self, x:str):
        '''Set compression type'''
        self['series']['cname'] = x

    @property
    def clevel(self) -> int:
        '''Get compression level'''
        return int(self['series']['clevel'])

    @clevel.setter
    def clevel(self, x:int):
        '''Set compression level'''
        self['series']['clevel'] = x


    def chunkshape(self, level=None) -> tuple:
        '''Get chunk shape.'''
        if level == None: level = self.level
        return tuple(self['series']['chunkshape'][level])

    def set_chunkshape(self, x, level:str=None):
        '''Set chunk shape.'''
        if level == None: level = self.level
        self['series']['chunkshape'][level] = x

    @property
    def brightness(self):
        return self['rendering']['brightness']

    @brightness.setter
    def brightness(self, v:float):
        self['rendering']['brightness'] = v

    @property
    def contrast(self):
        return self['rendering']['contrast']

    @contrast.setter
    def contrast(self, v:float):
        self['rendering']['contrast'] = v

    @property
    def level(self):
        return self['current']['level']

    @level.setter
    def level(self, s:str):
        self['current']['level'] = s


    @property
    def scale(self):
        return self['current']['level']

    @scale.setter
    def scale(self, s):
        self['current']['level'] = s

    # @property
    # def gif_speed(self):
    #     return self['state']['gif_speed']
    #
    # @gif_speed.setter
    # def gif_speed(self, s):
    #     self['state']['gif_speed'] = s

    @property
    def series(self):
        '''Returns the original series info for the alignment'''
        return self['series']


    @property
    def quadrants(self):
        '''property previously called grid_custom_regions'''
        return self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['quadrants']

    @quadrants.setter
    def quadrants(self, lst):
        '''property previously called grid_custom_regions'''
        # for level in self.levels():
        self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings']['method_opts']['quadrants'] = lst
        self.signals.dataChanged.emit()

    @property
    def padlock(self):
        '''Get time stamp, created.'''
        return self['state']['padlock']

    @padlock.setter
    def padlock(self, b):
        '''Get time stamp, created.'''
        self['state']['padlock'] = b

    def get_grid_custom_regions(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        assert self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method'] == 'grid'
        return self['stack'][l]['levels'][s]['swim_settings']['method_opts']['quadrants']

    def get_grid_regions(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        assert self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method'] == 'grid'
        return self['stack'][l]['levels'][s]['swim_settings']['method_opts']['quadrants']


    @property
    def poly_order(self):
        return self['level_data'][self.level]['output_settings']['polynomial_bias']

    @poly_order.setter
    def poly_order(self, use):
        self['level_data'][self.level]['output_settings']['polynomial_bias'] = use
        self.signals.dataChanged.emit()

    # def whitening(self) -> float:
    #     '''Returns the Signal Whitening Factor for the Current Layer.'''
    #     return float(self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['whitening'])

    @property
    def whitening(self):
        return float(self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['whitening'])

    @whitening.setter
    def whitening(self, x):
        self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['whitening'] = float(x)
        self.signals.dataChanged.emit()

    #Todo this isn't right!
    @property
    def defaults(self):
        return self['defaults'][self.level]

    @defaults.setter
    def defaults(self, d, level=None):
        if level == None:
            level = self.level
        self['defaults'][level] = d

    # layer['swim_settings']].setdefault('karg', False)

    @property
    def gif(self):
        name, _ = os.path.splitext(self.basename)
        return os.path.join(self.data_location, 'gif', self.level, name + '.gif')

    def writeDir(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        # cafm_hash = str(self.cafmHash(s=s, l=l))
        # path = os.path.join(self.data_location, 'data', str(l), s, ss_hash, cafm_hash)
        path = os.path.join(self.data_location, 'data', str(l), s, ss_hash)
        return path

    def writeDirCafm(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssSavedHash(s=s, l=l))
        cafm_hash = str(self.cafmHash(s=s, l=l))
        path = os.path.join(self.data_location, 'data', str(l), s, ss_hash, cafm_hash)
        return path

    def ssDir(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        path = os.path.join(self.data_location, 'data', str(l), s, ss_hash)
        return path

    def ssSavedDir(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssSavedHash(s=s, l=l))
        path = os.path.join(self.data_location, 'data', str(l), s, ss_hash)
        return path

    def isAligned(self, s=None, l=None) -> bool:
        if s == None: s = self.level
        if l == None: l = self.zpos
        path = os.path.join(self.ssSavedDir(), 'results.json')
        return os.path.exists(path)

    def path(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return os.path.join(self.series_location, 'tiff', s, self.name(s=s, l=l))

    def path_ref(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        if l == self.first_unskipped():
            return self.path(s=s, l=l)
        else:
            return os.path.join(self.series_location, 'tiff', s, self.name_ref(s=s, l=l))

    def path_zarr_transformed(self, s=None):
        if s == None: s = self.level
        return os.path.join(self.data_location, 'zarr', s)

    def path_zarr_raw(self, s=None):
        if s == None: s = self.level
        return os.path.join(self.series_location, 'zarr', s)

    def path_aligned(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        # name = self.name(s=s, l=l)
        fn, ext = os.path.splitext(self.name(s=s, l=l))
        # path = os.path.join(self.writeDir(s=s, l=l), name)
        path = os.path.join(self.writeDir(s=s, l=l), fn + '.thumb' + ext)
        return path


    def path_aligned_cafm(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        name = self.name(s=s, l=l)
        path = os.path.join(self.writeDirCafm(s=s, l=l), name)
        return path

    def path_aligned_cafm_thumb(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        # name = self.name(s=s, l=l)
        fn, ext = os.path.splitext(self.name(s=s, l=l))
        path = os.path.join(self.writeDir(s=s, l=l), fn + '.cafm.thumb' + ext)
        return path

    def path_aligned_cafm_thumb_ref(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        # name = self.name(s=s, l=l)
        i = self.get_ref_index(l=l)
        fn, ext = os.path.splitext(self.name(s=s, l=i))
        path = os.path.join(self.writeDir(s=s, l=i), fn + '.cafm.thumb' + ext)
        return path

    def path_thumb_src(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        path = os.path.join(self['info']['series_location'], 'thumbs', self.name(s=s, l=l))
        return path

    def path_thumb_src_ref(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        i = self.get_ref_index(l=l)
        path = os.path.join(self['info']['series_location'], 'thumbs', self.name(s=s, l=i))
        return path

    def path_thumb(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        fn, ext = os.path.splitext(self.name(s=s, l=l))
        path = os.path.join(self.writeDir(s=s, l=l), fn + '.thumb' + ext)
        return path

    def path_thumb_ref(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        i = self.get_ref_index(l=l)
        fn, ext = os.path.splitext(self.name(s=s, l=i))
        path = os.path.join(self.writeDir(s=s, l=i), fn + '.thumb' + ext)
        return path

    def path_gif(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        fn, ext = os.path.splitext(self.name(s=s, l=l))
        path = os.path.join(self.writeDir(s=s, l=l), fn + '.gif')
        return path

    def path_cafm_gif(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        fn, ext = os.path.splitext(self.name(s=s, l=l))
        path = os.path.join(self.writeDir(s=s, l=l), fn + '.cafm.gif')
        return path

    def dir_signals(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        path = os.path.join(self.data_location, 'data', str(l), s, ss_hash, 'signals')
        return path

    def dir_matches(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        path = os.path.join(self.data_location, 'data', str(l), s, ss_hash, 'matches')
        return path

    def dir_tmp(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        path = os.path.join(self.data_location, 'data', str(l), s, ss_hash, 'tmp')
        return path

    def section(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]


    def get_ref_index(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        # caller = inspect.stack()[1].function
        # logger.critical(f'caller: {caller}, z={z}')
        # if self.skipped(level=self.level, z=z):
        # if not self.include(s=self.level, l=l):
        #     return self.get_index(self._data['stack'][l]['levels'][self.level]['swim_settings']['path']) #Todo refactor this but not sure how
        # reference = self._data['stack'][l]['levels'][self.level]['swim_settings']['reference']
        # if reference == '':
        #     logger.warning('Reference is an empty string')
        #     return self.get_index(self._data['stack'][l]['levels'][self.level]['swim_settings']['path'])
        # return self.get_index(reference)
        return self.swim_settings(s=s, l=l)['reference_index']

    def is_zarr_generated(self, s=None):
        '''Returns whether Zarr has been generated/exported'''
        if s == None: s = self.level
        path = self.path_zarr_transformed(s=s)
        if os.path.exists(path):
            if os.path.exists(os.path.join(path,'.zarray')):
                return True
        return False


    def is_aligned(self, s=None):
        if s == None: s = self.level
        return sum(self.snr_list(s=s)) > 1.0 #Todo make this better


    def is_alignable(self) -> bool:
        '''Checks if the current scale is able to be aligned'''
        try:
            levels = self.levels
            cur_level = self.level
            coarsest_scale = levels[-1]
            if cur_level == coarsest_scale:
                # logger.info("is current level alignable? returning True")
                return True
            cur_scale_index = levels.index(cur_level)
            next_coarsest_scale_key = levels[cur_scale_index + 1]
            if not self.is_aligned(s=next_coarsest_scale_key):
                return False
            else:
                return True
        except:
            print_exception()

    def is_aligned_and_generated(self, s=None) -> bool:
        if s == None: s = self.level
        #Todo improve this, cache it or something

        # if level in get_scales_with_generated_alignments(self.levels):
        #     return True
        # else:
        #     return False
        try:
            if len(os.listdir(os.path.join(self.dest(), 'img_aligned.zarr', 's%d' % self.lvl()))) > 3:
                return True
            else:
                return False
        except:
            return False



    def numCorrSpots(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return len(self.snr_components())

    @property
    def t_scaling(self):
        return self['timings']['t_scaling']

    @t_scaling.setter
    def t_scaling(self, dt):
        self['timings']['t_scaling'] = dt

    @property
    def t_scaling_convert_zarr(self):
        return self['timings']['t_scaling_convert_zarr']

    @t_scaling_convert_zarr.setter
    def t_scaling_convert_zarr(self, dt):
        self['timings']['t_scaling_convert_zarr'] = dt

    @property
    def t_thumbs(self):
        return self['timings']['t_thumbs']

    @t_thumbs.setter
    def t_thumbs(self, dt):
        self['timings']['t_thumbs'] = dt

    @property
    def t_align(self):
        return self['timings']['levels'][self.level]['t_align']

    @t_align.setter
    def t_align(self, dt):
        self['timings']['levels'][self.level]['t_align'] = dt

    @property
    def t_generate(self):
        return self['timings']['levels'][self.level]['t_generate']

    @t_generate.setter
    def t_generate(self, dt):
        self['timings']['levels'][self.level]['t_generate'] = dt

    @property
    def t_convert_zarr(self):
        return self['timings']['levels'][self.level]['t_convert_zarr']

    @t_convert_zarr.setter
    def t_convert_zarr(self, dt):
        self['timings']['levels'][self.level]['t_convert_zarr'] = dt

    @property
    def t_thumbs_aligned(self):
        return self['timings']['levels'][self.level]['t_thumbs_aligned']

    @t_thumbs_aligned.setter
    def t_thumbs_aligned(self, dt):
        self['timings']['levels'][self.level]['t_thumbs_aligned'] = dt

    @property
    def t_thumbs_spot(self):
        return self['timings']['levels'][self.level]['t_thumbs_spot']

    @t_thumbs_spot.setter
    def t_thumbs_spot(self, dt):
        self['timings']['levels'][self.level]['t_thumbs_spot'] = dt

    @property
    def t_thumbs_matches(self):
        return self['timings']['levels'][self.level]['t_thumbs_matches']

    @t_thumbs_matches.setter
    def t_thumbs_matches(self, dt):
        self['timings']['levels'][self.level]['t_thumbs_matches'] = dt

    def normalize(self):
        return self['rendering']['neuroglancer']['normalize']

    def set_normalize(self, range):
        self['rendering']['neuroglancer']['normalize'] = range

    def notes(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['notes']

    def save_notes(self, text, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        self._data['stack'][l]['notes'] = text

    def sl(self):
        return (self.level, self.zpos)

    def to_json(self):
        return json.dumps(self._data)

    def to_dict(self):
        return self._data

    def base_image_name(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        # logger.info(f'Caller: {inspect.stack()[1].function}, level={level}, z={z}')
        return self._data['stack'][l]['levels'][s]['swim_settings']['name']

    '''NEW METHODS USING NEW DATA SCHEMA 2023'''


    def name(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['name']

    def name_ref(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        # i = self.swim_settings(s=s, l=l)['reference_index']
        try:
            return self.swim_settings(s=s, l=l)['reference_name']
        except:
            print_exception(extra=f'Section #{l}')
        # return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['reference'])


    def basefilenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.basename(p) for p in self.series['paths']])


    def clobber(self):
        return self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['clobber']

    def set_clobber(self, b, s=None, l=None, glob=False):
        if s == None: s = self.level
        if l == None: l = self.zpos
        if isinstance(b, bool):
            if glob:
                for s in self.scales:
                    for i in range(len(self)):
                        self['stack'][i]['levels'][s]['swim_settings']['clobber_size'] = b
            else:
                cur = self._data['stack'][l]['levels'][s]['swim_settings']['clobber']
                self['stack'][l]['levels'][s]['swim_settings']['clobber'] = b
                if cur != b:
                    self.signals.dataChanged.emit()

    def clobber_px(self):
        return self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['clobber_size']

    def set_clobber_px(self, x, s=None, l=None, glob=False):
        if s == None: s = self.level
        if l == None: l = self.zpos
        if isinstance(x,int):
            if glob:
                for s in self.scales:
                    for i in range(len(self)):
                        self['stack'][i]['levels'][s]['swim_settings']['clobber_size'] = x
            else:
                cur = self._data['stack'][l]['levels'][s]['swim_settings']['clobber_size']
                self._data['stack'][l]['levels'][s]['swim_settings']['clobber_size'] = x
                if cur != x:
                    self.signals.dataChanged.emit()

    def get_signals_filenames(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        dir_signals = self.dir_signals(s=s, l=l)
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        filename, extension = os.path.splitext(basename)
        pattern = '%s_%s_*%s' % (filename, self.current_method, extension)
        paths = os.path.join(dir_signals, pattern)
        names = natural_sort(glob(paths))
        return names

    def get_enum_signals_filenames(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        d = self.dir_signals(s=s, l=l)
        fn, ext = os.path.splitext(self.base_image_name(s=s, l=l))
        m = self.current_method
        # pattern = '%s_%s_*%s' % (fn, self.current_method, ext)
        # paths = natural_sort(glob(os.path.join(dir_signals, pattern)))
        paths = [os.path.join(d, '%s_%s_%d%s' % (fn, m, i, ext)) for i in range(0, 4)]
        return paths

    def get_matches_filenames(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        dir_matches = self.dir_matches(s=s, l=l)
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        filename, extension = os.path.splitext(basename)
        paths_t = glob(os.path.join(dir_matches, '%s_%s_t_[012]%s' % (filename, self.current_method, extension)))
        paths_k = glob(os.path.join(dir_matches, '%s_%s_k_[012]%s' % (filename, self.current_method, extension)))
        names = paths_t + paths_k
        return natural_sort(names)

    def get_grid_filenames(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        p = self.dir_signals(s=s, l=l)
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        fn, ex = os.path.splitext(basename)
        paths = [os.path.join(p, '%s_grid_%s%s' % (fn, i, ex)) for i in range(0,4)]
        return natural_sort(paths)

    def smallest_scale(self):
        return self.levels[-1]

    def layer_dict(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]

    # def first_cafm_false(self):
    #     for l in range(len(self)):
    #         if not self.is_zarr_generated(l=l):
    #             logger.info(f'returning {l}')
    #             return l
    #     return None


    def isRefinement(self, level=None):
        if level == None: level = self.level
        return level != self.coarsest_scale_key()

    # def get_source_img_paths(self):
    #     imgs = []
    #     for f in self.filenames():
    #         imgs.append(os.path.join(self.source_path(), os.path.basename(f)))
    #     return imgs

    def is_mendenhall(self):
        return self['data']['mendenhall']

    def get_iter(self, s=None, start=0, end=None):
        if s == None: s = self.level
        return ScaleIterator(self['stack'][start:end])

    def references_list(self):
        return [x['levels'][self.level]['swim_settings']['reference'] for x in self.get_iter()]

    def transforming_list(self):
        return [x['levels'][self.level]['swim_settings']['path'] for x in self.get_iter()]

    def transforming_bn_list(self):
        return [os.path.basename(x['levels'][self.level]['swim_settings']['path']) for x in self.get_iter()]

    def get_index(self, filename):
        # logger.info(f'[{inspect.stack()[1].function}] path = {path}')
        # logger.info(f'path = {path}')
        bn = os.path.basename(filename)
        return self.transforming_bn_list().index(bn)

    def get_ref_index_offset(self, l=None):
        if l == self.first_unskipped():  #1007+
            return 0                     #1007+
        if l == None:
            l = self.zpos
        return l - self.get_ref_index(l=l)


    def datetime(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['results']['datetime']
        except:
            return ''

    @property
    def timings(self):
        try:
            t0 = (f"%.1fs" % self['timings']['t_scaling']).rjust(12)
            t0m = (f"%.3fm" % (self['timings']['t_scaling'] / 60))
        except:
            t0 = t0m = "???"

        try:
            t1 = (f"%.1fs" % self['timings']['t_scaling_convert_zarr']).rjust(12)
            t1m = (f"%.3fm" % (self['timings']['t_scaling_convert_zarr'] / 60))
        except:
            t1 = t1m = "???"

        try:
            t2 = (f"%.1fs" % self['timings']['t_thumbs']).rjust(12)
            t2m = (f"%.3fm" % (self['timings']['t_thumbs'] / 60))
        except:
            t2 = t2m = "???"

        t3, t4, t5, t6, t7, t8 = {}, {}, {}, {}, {}, {}
        t3m, t4m, t5m, t6m, t7m, t8m = {}, {}, {}, {}, {}, {}
        for s in self.levels:

            try:
                t3[s] = (f"%.1fs" % self['timings']['levels'][s]['t_align']).rjust(12)
                t3m[s] = (f"%.3fm" % (self['timings']['levels'][s]['t_align'] / 60))
            except:
                t3[s] = t3m[s] = "???"

            try:
                t4[s] = (f"%.1fs" % self['timings']['levels'][s]['t_convert_zarr']).rjust(12)
                t4m[s] = (f"%.3fm" % (self['timings']['levels'][s]['t_convert_zarr'] / 60))
            except:
                t4[s] = t4m[s] = "???"

            try:
                t5[s] = (f"%.1fs" % self['timings']['levels'][s]['t_generate']).rjust(12)
                t5m[s] = (f"%.3fm" % (self['timings']['levels'][s]['t_generate'] / 60))
            except:
                t5[s] = t5m[s] = "???"

            try:
                t6[s] = (f"%.1fs" % self['timings']['levels'][s]['t_thumbs_aligned']).rjust(12)
                t6m[s] = (f"%.3fm" % (self['timings']['levels'][s]['t_thumbs_aligned'] / 60))
            except:
                t6[s] = t6m[s] = "???"

            try:
                t7[s] = (f"%.1fs" % self['timings']['levels'][s][
                    't_scale_generate']).rjust(12)
                t7m[s] = (f"%.3fm" % (self['timings']['levels'][s][
                                        't_scale_generate'] / 60))
            except:
                t7[s] = t7m[s] = "???"

            try:
                t8[s] = (f"%.1fs" % self['timings']['levels'][s][
                    't_scale_convert']).rjust(12)
                t8m[s] = (f"%.3fm" % (self['timings']['levels'][s][
                                        't_scale_convert'] / 60))
            except:
                t8[s] = t8m[s] = "???"

        timings = []
        # timings.append(('Generate Scale Hierarchy', t0 + ' / ' + t0m))
        # timings.append(('Convert All Scales to Zarr', t1 + ' / ' + t1m))
        # timings.append(('Generate Source Image Thumbnails', t2 + ' / ' + t2m))

        timings.append(('Generate Scales', t0 + ' / ' + t0m + " (total)"))
        for s in self.levels[1:]:
            timings.append(('  ' + self.level_pretty(s), '%s / %s' % (t7[s], t7m[s])))
        timings.append(('Convert Scales to Zarr', t1 + ' / ' + t1m + " (total)"))
        for s in self.levels:
            timings.append(('  ' + self.level_pretty(s), '%s / %s' % (t8[s], t8m[s])))
        timings.append(('Compute Affines', ''))
        for s in self.levels:
            timings.append(('  ' + self.level_pretty(s), '%s / %s' % (t3[s], t3m[s])))
        timings.append(('Generate Aligned TIFFs', ''))
        for s in self.levels:
            timings.append(('  ' + self.level_pretty(s), '%s / %s' % (t4[s], t4m[s])))
        timings.append(('Convert Aligned TIFFs to Zarr', ''))
        for s in self.levels:
            timings.append(('  ' + self.level_pretty(s), '%s / %s' % (t5[s], t5m[s])))
        timings.append(('Generate Aligned TIFF Thumbnails', ''))
        for s in self.levels:
            timings.append(('  ' + self.level_pretty(s), '%s / %s' % (t6[s], t6m[s])))
        return timings


    def snr(self, s=None, l=None, method=None) -> float:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            components = self['stack'][l]['levels'][s]['results']['snr']
            if type(components) == float:
                return components
            else:
                return statistics.fmean(map(float, components))
        except:
            tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            exi = sys.exc_info()
            txt = f" [{tstamp}] Error Type/Value : {exi[0]} / {exi[1]}"
            logger.warning(f"{txt}\nresolution level: {s}\n[{l}] Unable to return SNR. Returning 0.0")
            return 0.0


    def snr_list(self, s=None) -> list[float]:
        try:
            return [self.snr(s=s, l=i) for i in range(len(self))]
        except:
            logger.warning(f'No SNR Data Found. Returning 0s List [caller: {inspect.stack()[1].function}]...')
            print_exception()
            return [0] * len(self)


    def delta_snr_list(self, before, after):
        return [a_i - b_i for a_i, b_i in zip(before, after)]


    def snr_components(self, s=None, l=None, method=None) -> list[float]:
        caller = inspect.stack()[1].function
        if s == None: s = self.level
        if l == None: l = self.zpos
        if method == None:
            method = self.method(l=l)
        if l == 0:
            return []
        try:
            components = self._data['stack'][l]['levels'][s]['results']['snr']
            if type(components) == list:
                return components
            else:
                return [components]
        except:
            logger.warning(f'No SNR components for section {l}, method {method} [caller: {caller}]...\n')
            return []


    def snr_report(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        caller = inspect.stack()[1].function
        logger.info(f"[{caller}]")
        #Todo called too frequently by snr_errorbar_size
        try:
            method = self.method(s=s, l=l)
            return self._data['stack'][l]['levels'][s]['results']['snr_report']
        except:
            logger.warning('No SNR Report for Layer %d' % l)
            return ''


    def snr_errorbar_size(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            # if l == 0:
            #     return 0.0
            # report = self.snr_report(s=s, l=l)
            return self._data['stack'][l]['levels'][s]['results']['snr_std_deviation']
            # if not isinstance(report, str):
            #     logger.debug(f'No SNR Report Available For Layer {l}, Returning 0.0...')
            #     return 0.0
            # substr = '+-'
            # return float(report[report.index(substr) + 2: report.index(substr) + 5])
        except:
            print_exception()
            return 0.0


    def snr_errorbars(self, s=None):
        '''Note Length Of Return Array has size self.n_sections() - 1 (!)'''
        if s == None: s = self.level
        return np.array([self.snr_errorbar_size(s=s, l=l) for l in range(0, len(self))])


    def check_snr_status(self, s=None) -> list:
        if s == None: s = self.level
        unavailable = []
        for i,l in enumerate(self.stack(s=s)):
            if not 'snr' in l['results']:
                unavailable.append((i, self.name(s=s, l=i)))
        return unavailable


    def snr_max_all_scales(self) -> float:
        #Todo refactor, store local copy, this is a bottleneck
        max_snr = []
        try:
            for s in self.levels:
                if self.is_aligned(s=s):
                    m = max(self.snr_list(s=s)[1:]) #0601+ temp fix for self-alignment high SNR bug on first image
                    max_snr.append(m)
            return max(max_snr)
        except:
            caller = inspect.stack()[1].function
            logger.warning('Unable to append maximum SNR, none found (%s) - Returning Empty List' % caller)
            return 0.0


    def snr_lowest(self, n, s=None) -> zip:
        '''Returns the lowest n snr indices '''
        if s == None: s = self.level
        idx, val = zip(*nsmallest(n + 1, enumerate(self.snr_list()), key=itemgetter(1)))
        return zip(idx[1:], val[1:])


    def snr_average(self, scale=None) -> float:
        # logger.info('caller: %level...' % inspect.stack()[1].function)
        if scale == None: scale = self.level
        # NOTE: skip the first layer which does not have an SNR value level may be equal to zero
        try:
            return statistics.fmean(self.snr_list(s=scale)[1:])
        except:
            logger.warning('No SNR data found - returning 0.0...')
            return 0.0

    @property
    def current_method(self):
        try:
            if 'method_opts' in self['stack'][self.zpos]['levels'][self.level]['swim_settings']:
                return self['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['method']
            else:
                return None
        except:
            print_exception()
            return

    @current_method.setter
    def current_method(self, str):
        self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings']['method_opts']['method'] = str
        self.signals.dataChanged.emit()


    def method(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            if 'method_opts' in self['stack'][self.zpos]['levels'][self.level]['swim_settings']:
                return self['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['method']
            else:
                return None
        except:
            print_exception(extra=f"Section #{l}")

    def method_pretty(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        convert = {'grid': 'Grid Align', 'manual': 'Manual Align'}
        return convert[self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['method']]


    def manpoints(self, s=None, l=None):
        '''Returns manual correspondence points in Neuroglancer format'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['ng_coords']

    def set_manpoints(self, role, matchpoints, s=None, l=None):
        '''Sets manual correspondence points for a single section at the current level, and applies
         scaling factor then sets the same points for all scale levels above the current level.'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        logger.info(f"Writing manual points to project dictionary for section #{l}: {matchpoints}")
        # lvls  = [x for x in self.lvls() if x <= self.lvl()]
        # scales      = [get_scale_key(x) for x in lvls]
        glob_coords = [None,None,None]
        fac = self.lvl()
        for i,p in enumerate(matchpoints):
            if p:
                glob_coords[i] = (p[0] * fac, p[1] * fac)

        # set manual points in Neuroglancer coordinate system
        fac = self.lvl(s)
        coords = [None,None,None]
        for i,p in enumerate(glob_coords):
            if p:
                coords[i] = (p[0] / fac, p[1] / fac)
        logger.info(f'Setting manual points for {s}: {coords}')
        # self._data['stack'][z]['levels'][level]['swim_settings']['match_points'][role] = coords
        self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['ng_coords'][role] = coords

        # set manual points in MIR coordinate system
        img_width = self.image_size(s=s)[0]
        mir_coords = [None,None,None]
        for i,p in enumerate(coords):
            if p:
                mir_coords[i] = [img_width - p[1], p[0]]
        self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['mir_coords'][role] = mir_coords

    def manpoints_mir(self, role, s=None, l=None):
        '''Returns manual correspondence points in MIR format'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['mir_coords'][role]

    def manpoints_pretty(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        ref = [x for x in self.manpoints()['ref'] if x is not None]
        base = [x for x in self.manpoints()['tra'] if x is not None]
        return (['(%d, %d)' % (round(x1), round(y1)) for x1, y1 in ref],
                ['(%d, %d)' % (round(x1), round(y1)) for x1, y1 in base])


    def print_all_manpoints(self):
        logger.info('Match Points:')
        for i, sec in enumerate(self.stack()):
            r = sec['swim_settings']['method_opts']['points']['ng_coords']['ref']
            b = sec['swim_settings']['method_opts']['points']['ng_coords']['tra']
            if r != []:
                logger.info(f'Index: {i}, Ref, Match Points: {str(r)}')
            if b != []:
                logger.info(f'Index: {i}, Base, Match Points: {str(b)}')


    def getmpFlat(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        mps = self['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['ng_coords']
        # ref = [(0.5, x[0], x[1]) for x in mps['ref']]
        # base = [(0.5, x[0], x[1]) for x in mps['base']]

        d = {'ref': [None,None,None], 'tra': [None,None,None]}
        for i in range(0,3):
            try:
                if mps['ref'][i]:
                    d['ref'][i] = (l, mps['ref'][i][0], mps['ref'][i][1])
            except:
                print_exception()
            try:
                if mps['tra'][i]:
                    d['tra'][i] = (l, mps['tra'][i][0], mps['tra'][i][1])
            except:
                print_exception()

        # ref = [(z, x[0], x[1]) for x in mps['ref']]
        # base = [(z, x[0], x[1]) for x in mps['base']]
        return d


    def afm(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            # return self._data['stack'][z]['levels'][level]['alignment']['method_results']['affine_matrix']
            method = self.method(s=s,l=l)
            return self._data['stack'][l]['levels'][s]['results']['affine_matrix']
        except:
            print_exception()
            return [[[1, 0, 0], [0, 1, 0]]]


    def cafm(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            # return self._data['stack'][z]['levels'][level]['alignment']['method_results']['cumulative_afm'] #0802-
            # method = self.method(s=s, l=l)
            sss = self.saved_swim_settings(s=s, l=l)
            return self._data['stack'][l]['levels'][s]['cafm']
            # return self.ht_cafm.get(sss)
        except:
            # caller = inspect.stack()[1].function
            # print_exception(extra=f'Layer {z}, caller: {caller}')
            exi = sys.exc_info()
            logger.warning(f"[{l}] {exi[0]} {exi[1]}")
            # return [[1, 0, 0], [0, 1, 0]]


    def cafmHash(self, s=None, l=None):
        return abs(hash(str(self.cafm(s=s, l=l))))

    # if self.ht.haskey(self.saved_swim_settings()):
    #     d = self.ht.get(self.saved_swim_settings())


    def afm_list(self, s=None, l=None) -> list:
        if s == None: s = self.level
        lst = [self.afm(s=s, l=l) for l in range(len(self))]
        return lst


    def cafm_list(self, s=None, end=None) -> list:
        if s == None: s = self.level
        if end == None:
            end = len(self)
        lst = []
        for i in range(0,end):
            if i < end:
                lst.append(self.cafm(s=s, l=i))
        return lst

    def set_stack_cafm(self, s=None):
        if s == None: s = self.level
        SetStackCafm(self, scale=s, poly_order=self.poly_order)



    def cafm_registered_hash(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self['stack'][l]['levels'][s]['cafm_hash']


    # #Deprecated now registering cafm hash in SetStackCafm
    # def register_cafm_hashes(self, indexes, s=None):
    #     logger.info('Registering cafm data...')
    #     if s == None: s = self.level
    #     for i in indexes:
    #         self['stack'][i]['levels'][s]['cafm_hash'] = self.cafmHash(s=s, l=i)


    # def isdefaults(self, level=None, z=None):
    #     logger.info('')
    #     # if level == None: level = self.level
    #     # if z == None: z = self.zpos
    #     # caller = inspect.stack()[1].function
    #     # # logger.critical(f"caller: {caller}, level={level}, z={z}")
    #     # reasons = []
    #     # method = self.method(s=level, l=z)
    #     #
    #     # cur = self['stack'][z]['levels'][level]['swim_settings']  # current
    #     # dflts = self['defaults'][level]  # memory
    #     #
    #     # if method in ('manual_hint', 'manual_strict'):
    #     #     reasons.append((f"Uses manual alignment rather than default grid alignment", cur['method'], dflts['method']))
    #     #     answer = len(reasons) == 0
    #     #     return answer, reasons
    #     #
    #     # #Todo figure this out later
    #     # # if cur['reference'] != dflts['reference']:
    #     # #     reasons.append(('Reference images differ', cur['reference'], dflts['reference']))
    #     #
    #     # if cur['use_clobber'] != dflts['use_clobber']:
    #     #     reasons.append(("Inconsistent data at clobber fixed pattern ON/OFF (key: use_clobber)",
    #     #                      cur['use_clobber'],
    #     #                      dflts['use_clobber']))
    #     # elif (cur['use_clobber'] == True) and (dflts['use_clobber'] == True):
    #     #     if cur['clobber_size'] != dflts['clobber_size']:
    #     #         reasons.append(("Inconsistent data at clobber size in pixels (key: clobber_size)",
    #     #                          cur['clobber_size'], dflts['clobber_size']))
    #     #
    #     # else:
    #     #     if cur['whitening'] != dflts['whitening']:
    #     #         reasons.append(("Inconsistent data at signal whitening magnitude (key: whitening)",
    #     #                          cur['whitening'], dflts['whitening']))
    #     #     if cur['iterations'] != dflts['iterations']:
    #     #         reasons.append(("Inconsistent data at # SWIM iterations (key: swim_iters)",
    #     #                          cur['iterations'], dflts['iterations']))
    #     #
    #     # if 'grid' in method:
    #     #     keys = ['size_1x1', 'size_2x2', 'quadrants']
    #     #     for key in keys:
    #     #         if cur['grid'][key] != dflts['grid'][key]:
    #     #             reasons.append((f"Inconsistent data (key: {key})", cur['grid'][key], dflts['grid'][key]))
    #     #
    #     #
    #     # answer = len(reasons) == 0
    #     # logger.info(f"Returning {answer}, Reasons:\n{reasons}")
    #     # return answer, reasons
    #     return (False, [])

    def isDefaults(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        _cur = copy.deepcopy(cfg.data['stack'][l]['levels'][s]['swim_settings'])
        _def = copy.deepcopy(cfg.data['defaults'][s])
        to_remove = ('index', 'name', 'level', 'is_refinement', 'img_size', 'init_afm', 'reference_index', 'reference_name')
        for k in to_remove:
            _cur.pop(k, None)
        return _cur == _def



    # def data_comports(self, level=None, z=None):
    #     #Todo This will be an actual hash comparison
    #     if level == None: level = self.level
    #     if z == None: z = self.zpos
    #     # caller = inspect.stack()[1].function
    #
    #     # problems = []
    #     # method = self.method(s=level, l=z)
    #     #
    #     # #Temporary
    #     # if z == self.first_unskipped():
    #     #     return True, []
    #     #
    #     # # if not self['stack'][z]['levels'][level]['results']['complete']:
    #     # #     problems.append((f"Alignment method '{method}' is incomplete", 1, 0))
    #     # #     return False, problems
    #     #
    #     # cur = self['stack'][z]['levels'][level]['swim_settings']  # current
    #     # mem = self['stack'][z]['levels'][level]['alignment_history'][method]['swim_settings'] # memory
    #     #
    #     # #Todo refactor, 'recent_method' key
    #     # try:
    #     #     last_method_used = self['stack'][z]['levels'][level]['method_results']['method']
    #     #     if last_method_used != cur['method']:
    #     #         problems.append(('Method changed', last_method_used, cur['method']))
    #     # except:
    #     #     pass
    #     #
    #     # if cur['reference'] != mem['reference']:
    #     #     problems.append(('Reference images differ', cur['reference'], mem['reference']))
    #     #
    #     # if cur['use_clobber'] != mem['use_clobber']:
    #     #     problems.append(("Inconsistent data at clobber fixed pattern ON/OFF (key: use_clobber)", cur['use_clobber'],
    #     #                      mem['use_clobber']))
    #     # if cur['use_clobber']:
    #     #     if cur['clobber_size'] != mem['clobber_size']:
    #     #         problems.append(("Inconsistent data at clobber size in pixels (key: clobber_size)",
    #     #                          cur['clobber_size'], mem['clobber_size']))
    #     #
    #     # else:
    #     #     if cur['whitening'] != mem['whitening']:
    #     #         problems.append(("Inconsistent data at signal whitening magnitude (key: whitening)",
    #     #                          cur['whitening'], mem['whitening']))
    #     #     if cur['iterations'] != mem['iterations']:
    #     #         problems.append(("Inconsistent data at # SWIM iterations (key: swim_iters)",
    #     #                          cur['iterations'], mem['iterations']))
    #     #
    #     # if 'grid' in method:
    #     #     keys = ['size_1x1', 'size_2x2', 'quadrants']
    #     #     for key in keys:
    #     #         if cur['method_opts'][key] != mem['method_opts'][key]:
    #     #             problems.append((f"Inconsistent data (key: {key})", cur['method_opts'][key], mem['method_opts'][key]))
    #     #
    #     # if method in ('manual_hint', 'manual_strict'):
    #     #     if cur['manual']['points']['mir_coords'] != mem['manual']['points']['mir_coords']:
    #     #         problems.append((f"Inconsistent match points",
    #     #                          cur['manual']['points']['mir_coords'], mem['manual']['points']['mir_coords']))
    #     #
    #     #     if method == 'manual_hint':
    #     #         if cur['method_opts']['size'] != mem['method_opts']['size']:
    #     #             problems.append((f"Inconsistent match region size (key: manual_swim_window_px)",
    #     #                              cur['method_opts']['size'], mem['method_opts']['size']))
    #     # answer = len(problems) == 0
    #     # self['stack'][z]['levels'][level]['data_comports'] = answer
    #     # return answer, problems
    #     # # return tuple(comports?, [(reason/key, val1, val2)])
    #     return (True, [])

    # def updateComportsKeys(self, one=False, forward=False, all=False, indexes=None):
        # logger.info(f"[{caller_name()}] Updating Comports Keys...")
        # if one:        to_update = range(self.zpos, self.zpos+1)
        # elif forward:  to_update = range(self.zpos, len(self))
        # elif indexes:  to_update = indexes
        # elif all:      to_update = range(0, len(self))
        # else:          to_update = range(self.zpos, self.zpos+1)
        # for i in to_update:
        #     _data_comports = self['stack'][i]['levels'][self.level]['data_comports']
        #     _cafm_comports = self['stack'][i]['levels'][self.level]['cafm_comports']
        #     data_comports = self.data_comports(level=self.level, z=i)[0]
        #     cafm_comports = self.is_zarr_generated(s=self.level, l=i)
        #     if _data_comports != data_comports:
        #         logger.critical(f"Changing 'data_comports' from {_data_comports} to {data_comports} for section #{i}")
        #     if _cafm_comports != cafm_comports:
        #         logger.critical(f"Changing 'data_comports' from {_cafm_comports} to {cafm_comports} for section #{i}")
        #     self['stack'][i]['levels'][self.level]['data_comports'] = data_comports
        #     self['stack'][i]['levels'][self.level]['cafm_comports'] = cafm_comports
        # pass


    # def data_comports_list(self, s=None):
    #     if s == None: s = self.level
    #     # return np.array([self.data_comports(level=level, z=z)[0] for z in range(0, len(self))]).nonzero()[0].tolist()
    #     return [self['stack'][i]['levels'][s]['data_comports'] for i in range(0,len(self))]


    # def data_dn_comport_indexes(self, s=None):
    #     if s == None: s = self.level
    #     t0 = time.time()
    #     # lst = [(not self.data_comports(level=level, z=z)[0]) and (not self.skipped(level=level, z=z)) for z in range(0, len(self))]
    #     # answer = np.array(lst).nonzero()[0].tolist()
    #     if not self.is_aligned(s=s):
    #         # return list(range(len(self)))
    #         return []
    #     answer = []
    #     for i in range(0, len(self)):
    #         if self.include(s=s, l=i):
    #             if not self['stack'][i]['levels'][s]['data_comports']:
    #                 answer.append(i)
    #     t1 = time.time()
    #     logger.info(f"dt = {time.time() - t0:.3g} ({t1 - t0:.3g}/{time.time() - t1:.3g})")
    #     return answer

    def needsAlignIndexes(self, s=None):
        if s == None: s = self.level
        #Todo make this not use global
        do = []
        for i in range(len(self)):
            if not self.ht.haskey(self.saved_swim_settings(s=s, l=i)):
                do.append(i)
        return do

    def hasUnsavedChangesIndexes(self, s=None):
        #Todo create warning for this
        if s == None: s = self.level
        answer = []
        for i in range(len(self)):
            if not self.ssSavedComports(s=s, l=i):
                answer.append(i)
        return answer


    def all_comports_indexes(self, s=None):
        if s == None: s = self.level
        t0 = time.time()
        # answer = []
        # for i in range(len(self)):
        #     if self['stack'][i]['levels'][s]['data_comports']:
        #         if self['stack'][i]['levels'][s]['cafm_comports']:
        #             answer.append(i)

        # answer = list(set(range(len(self))) - set(self.needsGenerateIndexes(level=level)) - set(self.data_dn_comport_indexes(
        #     level=level)))

        answer = list(set(list(range(len(self)))) - set(self.needsGenerateIndexes()))


        logger.info(f"dt = {time.time() - t0:.3g}")
        return answer


    # def cafm_comports_indexes(self, s=None):
    #     if s == None: s = self.level
    #     # return np.array([self.is_zarr_generated(level=level, z=z) for z in range(0, len(self))]).nonzero()[0].tolist()
    #     answer = []
    #     for i in range(len(self)):
    #         if self['stack'][i]['levels'][s]['cafm_comports']:
    #             answer.append(i)
    #     return answer


    def needsGenerateIndexes(self, s=None):
        if s == None: s = self.level
        t0 = time.time()
        answer = []
        # for i in range(len(self)):
        #     if self.include(s=s, l=i):
        #         if (not self['stack'][i]['levels'][s]['data_comports']) or (not self['stack'][i]['levels'][s]['cafm_comports']):
        #             answer.append(i)
        if not self.is_zarr_generated(s=s):
            return list(range(len(self)))


        for i in range(len(self)):
            if not self.zarrCafmHashComports(s=s, l=i):
                answer.append(i)


            # if self.include(s=s, l=i):
            #     # if not os.path.exists(self.path_aligned(s=s, l=i)):
            #     if not os.path.exists(self.path_aligned_cafm(s=s, l=i)):
            #         answer.append(i)

        data_dn_comport = self.needsAlignIndexes()
        if len(data_dn_comport):
            sweep = list(range(min(data_dn_comport),len(self)))
            answer = list(set(answer) | set(sweep))

        logger.info(f"dt = {time.time() - t0:.3g}")
        return answer

    # def needsGenerateSavedIndexes(self, s=None):
    #     if s == None: s = self.level
    #     t0 = time.time()
    #     answer = []
    #     # for i in range(len(self)):
    #     #     if self.include(s=s, l=i):
    #     #         if (not self['stack'][i]['levels'][s]['data_comports']) or (not self['stack'][i]['levels'][s]['cafm_comports']):
    #     #             answer.append(i)
    #     for i in range(len(self)):
    #         if self.include(s=s, l=i):
    #             # if not os.path.exists(self.path_aligned(s=s, l=i)):
    #             if not os.path.exists(self.path_aligned_cafm(s=s, l=i)):
    #                 answer.append(i)
    #
    #     data_dn_comport = self.needsAlignIndexes()
    #     if len(data_dn_comport):
    #         sweep = list(range(min(data_dn_comport), len(self)))
    #         answer = list(set(answer) | set(sweep))
    #
    #     logger.info(f"dt = {time.time() - t0:.3g}")
    #     return answer


    def level_pretty(self, s=None) -> str:
        if not s:
            s = self.level
        return 'Level %d' % self.lvl(s=s)

    def lvl(self, s:str = None) -> int:
        if not s:
            s = self.level
        return int(s[1:])

    def lvls(self) -> list[int]:
        return [int(k[1:]) for k in self.levels]

    def level_key(self, v=None):
        if not v:
            return self.lvl
        return 's%d' % v

    # def get_level_key(self):
    #     return self['current'].get('level')

    def resolution(self, s=None):
        if s == None: s = self.level
        return self['series']['resolution'][s]

    def set_resolution(self, s, res_x:int, res_y:int, res_z:int):
        if s == None: s = self.level
        self['series']['resolution'][s] = (res_z, res_y, res_x)


    def get_user_zarr_settings(self):
        '''Returns user settings for cname, clevel, chunkshape as tuple (in that order).'''
        return (self.cname, self.clevel, self.chunkshape())



    def downscales(self) -> list[str]:
        '''Get downscales list (similar to scales() but with scale_1 removed).
        Faster than O(n*m) performance.
        Preserves order of scales.'''
        downscales = natural_sort(self['series']['levels'])
        downscales.remove('s1')
        return downscales

    def skipped(self, s=None, l=None) -> bool:
        '''Called by get_axis_data'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            # return bool(self._data['stack'][z]['levels'][level]['skipped'])
            return not bool(self._data['stack'][l]['levels'][s]['swim_settings']['include'])
        except IndexError:
            logger.warning(f'Index {l} is out of range.')
        except KeyError:
            # print_exception()
            logger.warning('Returning False, but there was a KeyError')
            return False
        except:
            print_exception()


    def include(self, s=None, l=None) -> bool:
        if s == None: s = self.level
        if l == None: l = self.zpos
        return bool(self['stack'][l]['levels'][s]['swim_settings']['include'])


    def set_skip(self, b: bool, s=None, l=None) -> None:
        if s == None: s = self.level
        if l == None: l = self.zpos
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['stack'][l]['levels'][s]['skipped'] = b
        self._data['stack'][l]['levels'][s]['swim_settings']['include'] = not b


    def skips_list(self, level=None) -> list:
        '''Returns the list of excluded images for a level'''
        if level == None: level = self.level
        indexes, names = [], []
        try:
            for i in range(0,len(self)):
                if not self['stack'][i]['levels'][level]['swim_settings']['include']:
                    indexes.append(i)
                    names.append(os.path.basename(self['stack'][i]['levels'][level]['swim_settings']['path']))
            return list(zip(indexes, names))
        except:
            print_exception()
            logger.warning('Unable to To Return Skips List')
            return []

    def skips_indices(self, s=None) -> list:
        if s == None: s = self.level
        try:
            return list(list(zip(*self.skips_list(s=s)))[0])
        except:
            return []

    def skips_by_name(self, s=None) -> list[str]:
        '''Returns the list of skipped images for a level'''
        if s == None: s = self.level
        lst = []
        try:
            for i in range(len(self)):
                if not self.include(s=s,l=i):
                    f = os.path.basename(self['stack'][i]['levels'][s]['swim_settings']['path'])
                    lst.append(f)
            return lst
        except:
            logger.warning('Unable to To Return Skips By Name List')
            return []


    def swim_iterations(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['iterations']


    def set_swim_iterations(self, val, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        self._data['stack'][l]['levels'][s]['swim_settings']['iterations'] = val
        self.signals.dataChanged.emit()


    def swim_settings(self, s=None, l=None):
        '''Returns SWIM settings as a hashable dictionary'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return HashableDict(self._data['stack'][l]['levels'][s]['swim_settings'])
        # return self._data['stack'][l]['levels'][s]['swim_settings']

    def saved_swim_settings(self, s=None, l=None):
        '''Returns the Saved SWIM settings as a hashable dictionary'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return HashableDict(self._data['stack'][l]['levels'][s]['saved_swim_settings'])
        # return self._data['stack'][l]['levels'][s]['saved_swim_settings']

    def saveSettings(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        self._data['stack'][l]['levels'][s]['saved_swim_settings'].update(copy.deepcopy(
            self._data['stack'][l]['levels'][s]['swim_settings']))
        self.set_stack_cafm(s=s)


    def ssHash(self, s=None, l=None):
        '''Returns SWIM settings as a hashable dictionary'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        # return abs(hash(HashableDict(self.swim_settings(s=s, l=l))))
        return abs(hash(self.swim_settings(s=s, l=l)))

    def ssSavedHash(self, s=None, l=None):
        '''Returns the Saved SWIM settings as a hashable dictionary'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return abs(hash(self.saved_swim_settings(s=s, l=l)))

    def ssSavedComports(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self.ssHash(s=s, l=l) == self.ssSavedHash(s=s, l=l)

    def zarrCafmHashComports(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        fu = self.first_unskipped()
        if l == fu:
            return True
        cur_cafm_hash = str(self.cafmHash(s=s, l=l))
        zarr_cafm_hash = self.zattrs[str(l)][1]
        # if cur_cafm_hash == zarr_cafm_hash:
        #     logger.info(f"Cache hit {cur_cafm_hash}! Zarr is correct at index {l}.")
        return cur_cafm_hash == zarr_cafm_hash



    def set_whitening(self, f: float, s=None, l=None) -> None:
        '''Sets the Whitening Factor for the Current Layer.'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        self._data['stack'][l]['levels'][s]['swim_settings']['whitening'] = f
        self.signals.dataChanged.emit()

    def aa1x1(self, val):
        val = ensure_even(val)
        img_w, img_h = self.image_size(s=self.level)
        val_y = ensure_even(int((val / img_w) * img_h))
        self['defaults'][self.level]['method_opts']['size_1x1'] = [val, val_y]
        cfg.mw.tell(f"Setting default 1x1 SWIM window: x,y = {val},{val_y}")
        for i in range(len(self)):
            if self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['method'] == 'grid':
                self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['size_1x1'] = [val, val_y]

    def aa2x2(self, val):
        val = ensure_even(val)
        img_w, img_h = self.image_size(s=self.level)
        val_y = ensure_even(int((val / img_w) * img_h))
        self['defaults'][self.level]['method_opts']['size_2x2'] = [val, val_y]
        cfg.mw.tell(f"Setting default 2x2 SWIM window: x,y = {val},{val_y}")
        for i in range(len(self)):
            if self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['method'] == 'grid':
                self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['size_2x2'] = [val, val_y]

    def aaQuadrants(self, lst):
        cfg.mw.tell(f"Setting default SWIM grid quadrants: {lst}")
        self['defaults'][self.level]['method_opts']['quadrants'] = lst
        for i in range(len(self)):
            if self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['method'] == 'grid':
                self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['quadrants'] = lst

    def aaIters(self, val):
        cfg.mw.tell(f"Setting default SWIM iterations: {val}")
        self['defaults'][self.level]['iterations'] = val
        for i in range(len(self)):
            self['stack'][i]['levels'][self.level]['swim_settings']['iterations'] = val

    def aaWhitening(self, val):
        cfg.mw.tell(f"Setting default SWIM whitening factor: {val}")
        self['defaults'][self.level]['whitening'] = val
        for i in range(len(self)):
            self['stack'][i]['levels'][self.level]['swim_settings']['whitening'] = val

    def aaClobber(self, tup):
        if tup[0]:
            cfg.mw.tell(f"Setting default fixed-pattern noise clobber: {tup[0]}, {tup[1]}")
        else:
            cfg.mw.tell(f"Setting default fixed-pattern noise clobber: {tup[0]}")
        self['defaults'][self.level]['clobber'] = tup[0]
        self['defaults'][self.level]['clobber_size'] = tup[1]
        for i in range(len(self)):
            self['stack'][i]['levels'][self.level]['swim_settings']['clobber'] = tup[0]
            self['stack'][i]['levels'][self.level]['swim_settings']['clobber_size'] = tup[1]


    def swim_1x1_size(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        # return self.stack()[self.zpos]['swim_settings']]['grid-custom-px']
        assert self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method'] == 'grid'
        return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['size_1x1']

    def set_swim_1x1_size(self, pixels=None, silent=False):
        '''Sets the SWIM Window for the Current Section across all scales.'''
        # if pixels == None:
        #     self.set_auto_swim_windows_to_default(current_only=True)
        # if (pixels % 2) == 1:
        #     pixels -= 1
        #     if int(pixels/2) % 2 == 1:
        #         pixels -= 2
        pixels = ensure_even(pixels)
        img_w, img_h = self.image_size(s=self.level)
        pixels = pixels
        pixels_y = (pixels / img_w) * img_h
        self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['size_1x1'] = [pixels,pixels_y]
        if (self.swim_2x2_size()[0] * 2) > pixels:
            self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['size_2x2'] = [int(pixels / 2  + 0.5), int(pixels_y / 2 + 0.5)]
        if not silent:
            self.signals.dataChanged.emit()



    # def propagate_swim_1x1_custom_px(self, indexes:list):
    #     '''Sets the SWIM Window for the Current Section across all scales.'''
    #     # img_w, img_h = self.image_size(level=self.level)
    #     # logger.critical(f"caller: {caller_name()}")
    #     for l in indexes:
    #         pixels = self._data['stack'][l]['levels'][self.level]['swim_settings']['method_opts']['size_1x1']
    #         for s in self.finer_scales():
    #             sf = self.lvl() / self.lvl(s)
    #             self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['size_1x1'] = [int(pixels[0] * sf + 0.5), int(pixels[1] * sf + 0.5)]


    def swim_2x2_size(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        assert self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method'] == 'grid'
        return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['size_2x2']


    def set_swim_2x2_size(self, pixels=None, silent=False):
        '''Returns the SWIM Window in pixels'''
        caller = inspect.stack()[1].function
        # if pixels == None:
        #     self.set_auto_swim_windows_to_default(current_only=True)
        # if (pixels % 2) == 1:
        #     pixels -= 1
        pixels = ensure_even(pixels)

        img_w, img_h = self.image_size(s=self.level)
        pixels_y = (pixels / img_w) * img_h

        if (2 * pixels) <= self.swim_1x1_size()[0]:
            self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['size_2x2'] = [pixels, pixels_y]
        else:
            force_pixels = [int(self.swim_1x1_size()[0] / 2 + 0.5), int(self.swim_1x1_size()[1] / 2 + 0.5)]
            if (force_pixels[0] % 2) == 1:
                force_pixels[0] -= 1
                force_pixels[1] -= 1
            self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['size_2x2'] = force_pixels
        if not silent:
            self.signals.dataChanged.emit()


    # def propagate_swim_2x2_custom_px(self, indexes:list):
    #     '''Returns the SWIM Window in pixels'''
    #     # img_w, img_h = self.image_size(level=self.level)
    #     for l in indexes:
    #         pixels = self._data['stack'][l]['levels'][self.level]['swim_settings']['method_opts']['size_2x2']
    #         for s in self.finer_scales(include_self=False):
    #             sf = self.lvl() / self.lvl(s)  # level factor
    #             self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['size_2x2'] = [int(pixels[0]* sf+ 0.5),
    #                                                                                           int(pixels[1] * sf + 0.5)]


    def manual_swim_window_px(self, s=None, l=None) -> int:
        '''Returns the SWIM Window for the Current Layer.'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return int(self['stack'][l]['levels'][s]['swim_settings']['method_opts']['size'])

    def set_manual_swim_window_px(self, pixels=None, silent=False) -> None:
        '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
        logger.info(f'Setting Local SWIM Window to [{pixels}] pixels...')

        if (pixels % 2) == 1:
            pixels -= 1

        self['stack'][self.zpos]['levels'][self.level]['swim_settings']['method_opts']['size'] = pixels
        if not silent:
            self.signals.dataChanged.emit()

    # def propagate_manual_swim_window_px(self, indexes) -> None:
    #     '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
    #     # logger.info('Propagating swim regions to finer scales...')
    #     for l in indexes:
    #         pixels = self['stack'][l]['levels'][self.level]['swim_settings']['method_opts']['size']
    #         for s in self.finer_scales():
    #             sf = self.lvl() / self.lvl(s)  # level factor
    #             self['stack'][l]['levels'][s]['swim_settings']['method_opts']['size'] = int(pixels * sf + 0.5)
    #             #todo
    #             # self['stack'][z]['levels'][level]['swim_settings']['method_opts']['size'] = (
    #             #             np.array(pixels) * sf).astype(int).tolist()


    def image_size(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['series']['size_xy'][s])

    def size_xy(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['series']['size_xy'][s])

    def size_zyx(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['series']['size_zyx'][s])


    def has_bb(self, s=None) -> bool:
        '''Returns the Has Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.level
        return bool(self['level_data'][s]['output_settings']['bounding_box']['has'])


    def set_has_bb(self, b:bool, s=None):
        '''Returns the Has Bounding Rectangle On/Off State for the Current Scale.'''
        # logger.info(f'Setting HAS bb to {b}')
        if s == None: s = self.level
        self['level_data'][s]['output_settings']['bounding_box']['has'] = b


    def use_bb(self, s=None) -> bool:
        '''Returns the Use Bounding Rectangle On/Off.'''
        if s == None: s = self.level
        return bool(self['level_data'][s]['output_settings']['bounding_box']['use'])

    def set_use_bounding_rect(self, b: bool, s=None) -> None:
        '''Sets the Bounding Rectangle On/Off.'''
        logger.info(f'Setting use bounding box to: {b}')
        if s == None: s = self.level
        self['level_data'][s]['output_settings']['bounding_box']['use'] = bool(b)

    def set_bounding_rect(self, bounding_rect: list, s=None) -> None:
        if s == None: s = self.level
        self['level_data'][s]['output_settings']['bounding_box']['size'] = bounding_rect

    def set_calculate_bounding_rect(self, s=None):
        if s == None: s = self.level
        self.set_bounding_rect(ComputeBoundingRect(self))
        return self['level_data'][s]['output_settings']['bounding_box']['size']


    def coarsest_scale_key(self) -> str:
        '''Return the coarsest level key. '''
        #Confirmed
        return natural_sort(self['series']['levels'])[-1]


    def finer_scales(self, s=None, include_self=True):
        if s == None: s = self.level
        if include_self:
            return [self.level_key(x) for x in self.lvls() if x <= self.lvl(s=s)]
        else:
            return [self.level_key(x) for x in self.lvls() if x < self.lvl(s=s)]


    def first_unskipped(self, s=None):
        # logger.info(f"{caller_name()}")
        if s == None: s = self.level
        for section in self.get_iter(s=s):
            # print(section['levels'][s]['swim_settings'])
            if section['levels'][s]['swim_settings']['include']:
                return section['levels'][s]['swim_settings']['index']

    def linkReference(self, level):
        logger.critical('Linking reference sections...')
        skip_list = self.skips_indices(s=level)
        for layer_index in range(len(self)):
            j = layer_index - 1  # Find nearest previous non-skipped z
            while (j in skip_list) and (j >= 0):
                j -= 1
            if (j not in skip_list) and (j >= 0):
                ref = self.path(s=level, l=j)
                # self['stack'][layer_index]['levels'][level]['swim_settings']['reference'] = ref
                self['stack'][layer_index]['levels'][level]['swim_settings']['reference_index'] = j
                self['stack'][layer_index]['levels'][level]['swim_settings']['reference_name'] = os.path.basename(ref)
                self['stack'][layer_index]['levels'][level]['saved_swim_settings']['reference_index'] = j
                self['stack'][layer_index]['levels'][level]['saved_swim_settings']['reference_name'] = os.path.basename(ref)
        # self['stack'][self.first_unskipped(s=level)]['levels'][level]['swim_settings']['reference'] = ''  # 0804
        self['stack'][self.first_unskipped(s=level)]['levels'][level]['swim_settings']['reference_index'] = None
        self['stack'][self.first_unskipped(s=level)]['levels'][level]['swim_settings']['reference_name'] = None
        self['stack'][self.first_unskipped(s=level)]['levels'][level]['saved_swim_settings']['reference_index'] = None
        self['stack'][self.first_unskipped(s=level)]['levels'][level]['saved_swim_settings']['reference_name'] = None




    def getSWIMSettings(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss = self['stack'][l]['levels'][s]['swim_settings']
        logger.info('')
        d = {
            'clobber': ss['clobber'],
            'clobber_size': ss['clobber_size'],
            'method_opts': ss['method_opts'],
            'initial_rotation': ss['initial_rotation'],
            'iterations': ss['iterations'],
            'whitening': ss['whitening'],
        }
        return d


    def pushDefaultSettings(self, s=None):
        logger.info('')
        if s == None: s = self.scale
        new_settings = self.getSWIMSettings()
        self['defaults'][s].update(copy.deepcopy(new_settings))
        for l in range(0, len(self)):
            #Check if default settings are in use for each layer, if so, update with new settings
            if self.isDefaults(l=l):
                self['stack'][l]['levels'][self.level]['swim_settings'].update(copy.deepcopy(new_settings))
        self.signals.dataChanged.emit()

    def applyDefaults(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        def_settings = copy.deepcopy(self['defaults'][s])
        logger.info(f"Applying default settings...")
        self['stack'][l]['levels'][s]['swim_settings'].update(def_settings)
        self.signals.dataChanged.emit()

    def getSwimPresets(self) -> dict:
        logger.info('')

        d = {}
        d.update(
            # method=cfg.DEFAULT_METHOD,
            include=True,
            clobber=cfg.DEFAULT_USE_CLOBBER,
            clobber_size=cfg.DEFAULT_CLOBBER_PX,
            iterations=cfg.DEFAULT_SWIM_ITERATIONS,
            whitening=cfg.DEFAULT_WHITENING,
            initial_rotation=cfg.DEFAULT_INITIAL_ROTATION,
        )

        return d


    def getMethodPresets(self) -> dict:
        logger.info('')

        fullsize = np.array(self['series']['size_xy'][self.levels[0]], dtype=int)
        s1_size_1x1 = fullsize * cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC

        d = {v: {} for v in self.levels}
        for level, v in d.items():

            factor = int(level[1:])
            _1x1 = np.rint(s1_size_1x1 / factor).astype(int).tolist()
            _2x2 = np.rint(s1_size_1x1 / factor / 2).astype(int).tolist()
            # Temporary ^. Take first value only. This should perhaps be rectangular, two-value.
            _1x1 = ensure_even(_1x1, extra='1x1 size')
            _2x2 = ensure_even(_2x2, extra='2x2 size')
            man_ww_full = min(fullsize[0], fullsize[1]) * cfg.DEFAULT_MANUAL_SWIM_WINDOW_PERC
            _man_ww = ensure_even(man_ww_full / int(level[1:]))

            v.update(
                manual={
                    'method': 'manual',
                    'mode': 'hint',
                    'size': _man_ww,
                    'points':{
                        # 'ng_coords': {'tra': [], 'ref': []},
                        # 'mir_coords': {'tra': [], 'ref': []},
                        'ng_coords': {'tra': ((None, None), (None, None), (None, None)),
                                      'ref': ((None, None), (None, None), (None, None))},
                        'mir_coords': {'tra': ((None, None), (None, None), (None, None)),
                                       'ref': ((None, None), (None, None), (None, None))},
                    }
                },
                grid={
                    'method': 'grid',
                    'quadrants': [1,1,1,1],
                    'size_1x1': _1x1,
                    'size_2x2': _2x2,
                }
            )

        return d


    def initLevel(self, level):
        pass

    def pullSettings(self):
        levels = self.levels
        cur_level = self.level
        prev_level = levels[levels.index(cur_level) + 1]
        logger.critical(f'\n\nPulling settings from resolution level {prev_level} to {cur_level}...\n')
        # sf = self.lvl(cur_level) / self.lvl(prev_level)
        sf = int(self.lvl(prev_level) / self.lvl(cur_level))

        self['level_data'][cur_level]['output_settings'] = copy.deepcopy(
            self['level_data'][prev_level]['output_settings'])

        # Todo need to add 'Align All' functionality for manual alignment settings (region size)
        self['level_data'][cur_level]['method_presets'] = copy.deepcopy(
            self['level_data'][prev_level]['method_presets'])
        self['level_data'][cur_level]['method_presets']['grid']['size_1x1'][0] *= sf
        self['level_data'][cur_level]['method_presets']['grid']['size_2x2'][1] *= sf
        self['level_data'][cur_level]['method_presets']['manual'] = copy.deepcopy(
            self['level_data'][prev_level]['method_presets']['manual'])
        self['level_data'][cur_level]['method_presets']['manual']['size'] *= sf

        self['defaults'][cur_level].update(copy.deepcopy(self['defaults'][prev_level]))
        self['defaults'][cur_level]['method_opts']['size_1x1'][0] *= sf
        self['defaults'][cur_level]['method_opts']['size_1x1'][1] *= sf
        self['defaults'][cur_level]['method_opts']['size_2x2'][0] *= sf
        self['defaults'][cur_level]['method_opts']['size_2x2'][1] *= sf

        try:
            # for d in self():
            for i in range(len(self)):
                prev_settings = self.swim_settings(s=prev_level, l=i)
                self['stack'][i]['levels'][cur_level]['swim_settings'] = copy.deepcopy(prev_settings)
                ss = self['stack'][i]['levels'][cur_level]['swim_settings']
                try:
                    init_afm = copy.deepcopy(self.ht.get(self.saved_swim_settings(s=prev_level, l=i)))
                except:
                    print_exception(extra=f'Section #{i}. Using identity instead...')
                    init_afm = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()
                init_afm[0][2] *= sf
                init_afm[1][2] *= sf
                # ss = copy.deepcopy(prev_settings)
                # d['levels'][cur_level]['swim_settings']['img_size'] = self['series']['size_xy'][cur_level]
                ss['init_afm'] = init_afm
                mo = ss['method_opts']
                method = mo['method']
                if method == 'grid':
                    mo['size_1x1'][0] *= sf
                    mo['size_1x1'][1] *= sf
                    mo['size_2x2'][0] *= sf
                    mo['size_2x2'][1] *= sf
                elif method == 'manual':
                    mo['size'] *= sf
                    p1 = mo['points']['ng_coords']['tra']
                    p2 = mo['points']['ng_coords']['ref']
                    p3 = mo['points']['mir_coords']['tra']
                    p4 = mo['points']['mir_coords']['ref']
                    for i, p in enumerate(p1):
                        p1[i] = [(x * sf, y * sf) for x, y in p]
                    for i, p in enumerate(p2):
                        p2[i] = [(x * sf, y * sf) for x, y in p]
                    for i, p in enumerate(p3):
                        p3[i] = [(x * sf, y * sf) for x, y in p]
                    for i, p in enumerate(p4):
                        p4[i] = [(x * sf, y * sf) for x, y in p]
        except:
            print_exception()
        else:
            self['level_data'][cur_level]['alignment_ready'] = True
        logger.info(f"\n\n{pprint.pformat(self['stack'][i]['levels'][cur_level]['swim_settings'])}\n")


    def initializeStack(self, series_info, series_location, data_location):
        logger.critical(f"\n\nInitializing data model ({data_location})...\n")

        levels = natural_sort(series_info['levels'])
        paths = natural_sort(series_info['paths'])
        top_level = levels[0]
        bottom_level = levels[-1]
        identity_matrix = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()

        self._data.update(
            info={
                'series_location': series_location,
                'data_location': data_location,
                'version': cfg.VERSION,
                'created': date_time(),
                'system': {'node': platform.node()},
                'alignment_uuid': str(uuid.uuid4()),
                'series_uuid': series_info['uuid']
            },
            series=series_info,
            stack=[],
            # defaults={'levels': {v: {} for v in self.levels}},
            current={
                'level': bottom_level,
                'z_position': 0
            },
            # defaults={s: {} for s in levels},
            # defaults={},
            level_data={s: {} for s in levels},
            timings={
                'levels': {s: {} for s in levels},
                't_scaling': 0.0,
                't_scaling_convert_zarr': 0.0,
                't_thumbs': 0.0
            },
            state={
                'padlock': False,
                'current_tab': 0,
                'gif_speed': 100,
                'zarr_viewing': 'raw',
                'neuroglancer': {
                    'layout': '4panel',
                    'zoom': 1.0,
                    'blink': False,
                    'show_controls': False,
                    'show_bounds': True,
                    'show_axes': True,
                    'show_scalebar': True,
                    'region_selection': {
                        'select_by': 'cycle',  # cycle, zigzag, or sticky
                    }
                },
                'tra_ref_toggle': 1,
                'targ_karg_toggle': 1,
                'annotate_match_signals': True,
            },
            rendering={
                'normalize': [1, 255],
                'brightness': 0,
                'contrast': 0,
                'shader':
                    '''#uicontrol vec3 color color(default="white")
                    #uicontrol float brightness slider(min=-1, max=1, step=0.01)
                    #uicontrol float contrast slider(min=-1, max=1, step=0.01)
                    void main() { emitRGB(color * (toNormalized(getDataValue()) + brightness) * exp(contrast));}
                    '''
            },
            protected = {
                'results': {},
            },
            defaults={s: {} for s in levels}
        )

        for i in range(self.count):
            basename = os.path.basename(paths[i])
            self['stack'].append({})
            self['stack'][i].update(
                index=i,
                name=basename,
                path=paths[i],
                levels={s: {} for s in levels},
                # levels={bottom_level: {}},
                notes=''
            )
            for level in levels:
                self['stack'][i]['levels'][level].update(
                    data_comports=True,
                    cafm_comports=True,
                    cafm_hash=None,
                    cafm=identity_matrix,
                    saved_swim_settings={
                        'index': i,
                        'name': basename,
                        'level': level,
                        'include': True,
                        'is_refinement': self.isRefinement(level=level),
                        'img_size': self['series']['size_xy'][level],
                        'init_afm': identity_matrix,
                    },
                    swim_settings={
                        'index': i,
                        'name': basename,
                        'level': level,
                        'include': True,
                        'is_refinement': self.isRefinement(level=level),
                        'img_size': self['series']['size_xy'][level],
                        'init_afm': identity_matrix,
                    },
                    points_buffer=None,
                    results={
                        'snr': 0.0,
                        'snr_std_deviation': 0.0,
                        'snr_mean': 0.0,
                        'affine_matrix': identity_matrix,
                    }
                )
                self['level_data'][level].update(
                    initial_snr=None,
                    aligned=False,
                    alignment_ready=(level == self.coarsest_scale_key()),
                )

        swim_presets = self.getSwimPresets()
        method_presets = self.getMethodPresets()

        self['defaults'][bottom_level].update(copy.deepcopy(swim_presets), method_opts=copy.deepcopy(
            method_presets[bottom_level]['grid']))

        self['level_data'][bottom_level].update(
            #Todo output settings will need to propagate
            zarr_made=False,
            swim_presets=swim_presets,
            method_presets=method_presets[bottom_level],
            output_settings={
                'bounding_box': {
                    'use': False,
                    'has': False,
                    'size': None,
                },
                'polynomial_bias': cfg.DEFAULT_CORRECTIVE_POLYNOMIAL,
            },
            results={},
        )

        for i in range(len(self)):
            self['stack'][i]['levels'][bottom_level]['saved_swim_settings'].update(
                copy.deepcopy(swim_presets),
                method_opts=copy.deepcopy(method_presets[bottom_level]['grid']),
            )
            self['stack'][i]['levels'][bottom_level]['swim_settings'].update(
                copy.deepcopy(swim_presets),
                method_opts=copy.deepcopy(method_presets[bottom_level]['grid']),
            )


        self.linkReference(level=bottom_level)

    def setZarrMade(self, b, s=None):
        if s == None: s = self.level
        self['level_data'][s]['zarr_made'] = b

def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding. Faster than O(n*m) performance.'''
    convert = lambda text: int(text) if text.isdigit() else text.lower()
    alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
    return sorted(l, key=alphanum_key)

@dataclass
class StripNullFields:
    def asdict(self):
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                if hasattr(v, "asdict"):
                    result[k] = v.asdict()
                elif isinstance(v, list):
                    result[k] = []
                    for element in v:
                        if hasattr(element, "asdict"):
                            result[k].append(element.asdict())
                        else:
                            result[k].append(element)
                else:
                    result[k] = v
        return result


def hashstring(text:str):
    hash=0
    for ch in text:
        hash = ( hash*281  ^ ord(ch)*997) & 0xFFFFFFFF
    return hash

def dict_hash(dictionary: Dict[str, Any]) -> str:
    """Returns an MD5 hash of a Python dictionary. source:
    www.doc.ic.ac.uk/~nuric/coding/how-to-hash-a-dictionary-in-python.html"""
    dhash = hashlib.md5()
    encoded = json.dumps(dictionary, sort_keys=True).encode()
    dhash.update(encoded)
    return dhash.hexdigest()


def to_even(n):
    if (n % 2 != 0):
        return n + 1
    return n


def ensure_even(vals, extra=None):
    if isinstance(vals, int) or isinstance(vals, float):
        #integer
        vals = int(vals)
        try:
            assert vals % 2 == 0
        except:
            msg = f"Odd window size: {vals}. Adding one pixel to keep things even for SWIM."
            if extra: msg = f'[{extra}] ' + msg
            logger.warning(msg)
            vals += 1
            logger.info(f"Modified: {vals}")
    else:
        #iterable
        for i, x in enumerate(vals):
            vals[i] = int(vals[i])
            try:
                assert x % 2 == 0
            except:
                msg = f"Odd window size: {x}. Adding one pixel to keep things even for SWIM."
                if extra: msg = f'[{extra}] ' + msg
                logger.warning(msg)
                vals[i] += 1
                logger.info(f"Modified: {vals[i]}")
    return vals


class HashableDict(dict):
    def __hash__(self):
        # return abs(hash(str(sorted(self.items()))))
        return abs(hash(str(sorted(self.items()))))

if __name__ == '__main__':
    data = DataModel()
    print('Data Model Version: ' + str(data['version']))
    print(data)
