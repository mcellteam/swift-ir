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
import shutil
import numpy as np
from qtpy.QtCore import QObject, Signal, Slot, QMutex
from qtpy.QtWidgets import QApplication

from src.funcs_image import SetStackCafm
from src.helpers import print_exception, exist_aligned_zarr, get_scales_with_generated_alignments, getOpt, \
    caller_name
from src.funcs_image import ComputeBoundingRect, ImageSize, ImageIOSize
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
    warning2 = Signal()
    outputSettingsChanged = Signal()
    swimSettingsChanged = Signal()


class DataModel:

    """ Encapsulate datamodel dictionary and wrap with methods for convenience """
    def __init__(self, data=None, location=None, read_only=False, initialize=False, series_info=None):
        self._current_version = cfg.VERSION
        if data:
            self._data = data  # Load project data from file
        elif initialize:
            try:
                series_info
            except NameError:
                logger.warning(f"'series_info' argument is needed to initialize data model."); return
            try:
                location
            except NameError:
                logger.warning(f"'location' argument is needed to initialize data model."); return
            self._data = {}
            self.initializeStack(series_info=series_info, location=location)
        if not read_only:
            self._data['modified'] = date_time()
            if not initialize:
                self.updateComportsKeys(all=True)
            self.signals = Signals()
            self.signals.warning2.connect(lambda: logger.critical('emission!'))
            # self.signals.warning2.connect(lambda: self.updateComportsKeys(forward=True))
            self.signals.warning2.connect(lambda: self.updateComportsKeys(indexes=[self.zpos]))
        logger.info('<<')

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


    def to_file(self):
        path = os.path.join(self.dest(), 'state_' + date_time() + '.swiftir')
        with open(path, 'w') as f:
            f.write(str(self.to_json()))

    @property
    def count(self):
        return len(self)

    @property
    def name(self):
        return self['name']

    @property
    def basename(self) -> str:
        '''Get transforming image filename.'''
        return os.path.basename(self['stack'][self.zpos]['levels'][self.level]['swim_settings']['path'])

    @property
    def refname(self) -> str:
        '''Get reference image filename.'''
        return os.path.basename(self['stack'][self.zpos]['levels'][self.level]['swim_settings']['reference'])

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
    def location(self):
        '''Set alignment data location.'''
        return self['info']['location']

    @location.setter
    def location(self, p):
        '''Get alignment data location.'''
        self['info']['location'] = p

    def dest(self) -> str:
        return self['info']['location']

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
        return self['series']['chunkshape'][level]

    def set_chunkshape(self, x:tuple, level:str=None):
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

    @property
    def series(self):
        '''Returns the original series info for the alignment'''
        return self['series']

    @property
    def current_method(self):
        try:
            return self['stack'][self.zpos]['levels'][self.level]['swim_settings']['method']
        except:
            print_exception()


    @current_method.setter
    def current_method(self, str):
        for s in self.finer_scales():
            self._data['stack'][self.zpos]['levels'][s]['swim_settings']['method'] = str
        self.signals.warning2.emit()


    @property
    def current_method_pretty(self):
        convert = {
            'grid_default': 'Grid Default',
            'grid_custom': 'Grid Custom',
            'manual_hint': 'Correspondence Points, Hint',
            'manual_strict': 'Correspondence Points, Strict'
        }
        return convert[self.current_method]

    @property
    def quadrants(self):
        '''property previously called grid_custom_regions'''
        return self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['grid']['quadrants']

    @quadrants.setter
    def quadrants(self, lst):
        '''property previously called grid_custom_regions'''
        # for level in self.levels():
        for s in self.finer_scales():
            self._data['stack'][self.zpos]['levels'][s]['swim_settings']['grid']['quadrants'] = lst
        self.signals.warning2.emit()

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
        return self['stack'][l]['levels'][s]['swim_settings']['grid']['quadrants']

    def get_grid_regions(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self['stack'][l]['levels'][s]['swim_settings']['grid']['quadrants']


    @property
    def poly_order(self):
        return self['level_data'][self.level]['output_settings']['polynomial_bias']

    @poly_order.setter
    def poly_order(self, use):
        self['level_data'][self.level]['output_settings']['polynomial_bias'] = use
        self.signals.warning2.emit()

    # def whitening(self) -> float:
    #     '''Returns the Signal Whitening Factor for the Current Layer.'''
    #     return float(self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['whitening'])

    @property
    def whitening(self):
        return float(self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['whitening'])

    @whitening.setter
    def whitening(self, x):
        self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['whitening'] = float(x)
        self.signals.warning2.emit()

    @property
    def defaults(self):
        return self['defaults'][self.level]

    @defaults.setter
    def defaults(self, d, level=None):
        if level == None:
            level = self.level
        self['defaults'][level] = d

    @property
    def defaults_pretty(self):
        d = self['defaults'][self.level]
        defaults_str = ''
        nl = '\n'
        defaults_str += f"Initial Rotation: {d['initial_rotation']}\n" \
                        f"SWIM Window Dimensions:\n{nl.join(['  %s: %s' % (s.ljust(9), '%sx%s' % tuple(d['window_size'])) for s in self.levels])}\n" \
                        f"SWIM iterations: {d['iterations']}\n" \
                        f"SWIM Signal Whitening: {d['whitening']}"
        return defaults_str

    # layer['swim_settings']].setdefault('karg', False)


    @property
    def gif(self):
        name, _ = os.path.splitext(self.basename)
        return os.path.join(self.location, 'gif', self.level, name + '.gif')

    def section(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]


    def get_ref_index(self, l=None):
        if l == None: l = self.zpos
        caller = inspect.stack()[1].function
        # logger.critical(f'caller: {caller}, z={z}')
        # if self.skipped(level=self.level, z=z):
        if not self.include(s=self.level, l=l):
            return self.get_index(self._data['stack'][l]['levels'][self.level]['swim_settings']['path']) #Todo refactor this but not sure how
        reference = self._data['stack'][l]['levels'][self.level]['swim_settings']['reference']
        if reference == '':
            logger.warning('Reference is an empty string')
            return self.get_index(self._data['stack'][l]['levels'][self.level]['swim_settings']['path'])
        return self.get_index(reference)

    # @cache
    def is_aligned(self, s=None):
        if s == None: s = self.level
        return sum(self.snr_list()) > 1.0 #Todo make this better


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
        return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['path'])

    '''NEW METHODS USING NEW DATA SCHEMA 2023'''

    def filename(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['path']


    def filename_basename(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['path'])

    def reference_basename(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['reference'])

    def basefilenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.basename(p) for p in self.series['paths']])

    def thumbnail_ref(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        return os.path.join(self.dest(), 'thumbnails', os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings'][
            'reference']))

    def thumbnail_tra(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        return os.path.join(self.dest(), 'thumbnails', os.path.basename(self._data['stack'][l]['levels'][s][
                                                                            'swim_settings']['path']))
    def thumbnail_aligned(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        '''Returns absolute path of thumbnail for current layer '''
        return os.path.join(self.dest(), 'thumbnails', self.level, self.filename_basename(s=s,l=l))

    def clobber(self):
        return self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['clobber_fixed_noise']

    def set_clobber(self, b, scales=None, stack=False):
        if isinstance(b, bool):
            if scales == None: scales = self.finer_scales()
            for s in scales:
                if stack:
                    for i in range(len(self)):
                        self['stack'][i]['levels'][s]['swim_settings']['clobber_fixed_noise'] = b
                else:
                    self['stack'][self.zpos]['levels'][s]['swim_settings']['clobber_fixed_noise'] = b
            self.signals.warning2.emit()

    def clobber_px(self):
        return self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['clobber_size']

    def set_clobber_px(self, x, scales=None, stack=False):
        if isinstance(x,int):
            if scales == None: scales = self.finer_scales()
            for s in scales:
                if stack:
                    for i in range(len(self)):
                        self['stack'][i]['levels'][s]['swim_settings']['clobber_size'] = x
                    self.signals.warning2.emit()

                else:
                    cur = self._data['stack'][self.zpos]['levels'][s]['swim_settings']['clobber_size']
                    self._data['stack'][self.zpos]['levels'][s]['swim_settings']['clobber_size'] = x
                    if cur != x:
                        self.signals.warning2.emit()
            self.signals.warning2.emit()

    def get_signals_filenames(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        # caller = inspect.stack()[1].function
        dir = os.path.join(self.dest(), 'signals', s)
        # logger.info(f"[{caller}] dir: {dir}")
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        filename, extension = os.path.splitext(basename)
        pattern = '%s_%s_*%s' % (filename, self.current_method, extension)
        # logger.info(f"[{caller}] pattern: {pattern}")
        paths = os.path.join(dir, pattern)
        names = natural_sort(glob(paths))
        # logger.info(f'Search Path: {paths}\nReturning: {names}')
        # logger.info(f"[{caller}] Returning: {names}")
        return names

    def get_matches_filenames(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        dir = os.path.join(self.dest(), 'matches', s)
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        filename, extension = os.path.splitext(basename)
        paths_t = glob(os.path.join(dir, '%s_%s_t_[012]%s' % (filename, self.current_method, extension)))
        paths_k = glob(os.path.join(dir, '%s_%s_k_[012]%s' % (filename, self.current_method, extension)))
        names = paths_t + paths_k
        # logger.info(f'Returning: {names}')
        return natural_sort(names)

    def get_grid_custom_filenames(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        dir = os.path.join(self.dest(), 'signals', s)
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        filename, extension = os.path.splitext(basename)
        paths = []
        paths.append(os.path.join(dir, '%s_grid-custom_0%s' % (filename, extension)))
        paths.append(os.path.join(dir, '%s_grid-custom_1%s' % (filename, extension)))
        paths.append(os.path.join(dir, '%s_grid-custom_2%s' % (filename, extension)))
        paths.append(os.path.join(dir, '%s_grid-custom_3%s' % (filename, extension)))
        # logger.info(f'Search Path: {paths}\nReturning: {names}')
        return natural_sort(paths)

    def smallest_scale(self):
        return self.levels[-1]

    def layer_dict(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]

    def first_cafm_false(self):
        for l in range(len(self)):
            if not self.cafm_hash_comports(l=l):
                logger.info(f'returning {l}')
                return l
        return None


    def isRefinement(self):
        return  self.level != self.coarsest_scale_key()

    def get_source_img_paths(self):
        imgs = []
        for f in self.filenames():
            imgs.append(os.path.join(self.source_path(), os.path.basename(f)))
        return imgs

    def is_mendenhall(self):
        return self['data']['mendenhall']

    def get_iter(self, s=None, start=0, end=None):
        if s == None: s = self.level
        return ScaleIterator(self['stack'][start:end])

    def references_list(self):
        return [x['levels'][self.level]['swim_settings']['reference'] for x in self.get_iter()]

    def transforming_list(self):
        return [x['levels'][self.level]['swim_settings']['path'] for x in self.get_iter()]

    def get_index(self, filename):
        # logger.info(f'[{inspect.stack()[1].function}] filename = {filename}')
        # logger.info(f'filename = {filename}')
        return self.transforming_list().index(filename)

    def get_ref_index_offset(self, l=None):
        if l == None:
            l = self.zpos
        return l - self.get_ref_index(l=l)


    def datetime(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['method_results']['datetime']
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
        if method == None:
            method = self['stack'][l]['levels'][s]['swim_settings']['method']
        try:
            components = self['stack'][l]['levels'][s]['alignment_history'][method]['method_results']['snr']
            if type(components) == float:
                return components
            else:
                return statistics.fmean(map(float, components))
        except:
            tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            exi = sys.exc_info()
            txt = f" [{tstamp}] Error Type/Value : {exi[0]} / {exi[1]}"
            logger.warning(f"{txt}\n[{l}] Unable to return SNR. Returning 0.0")
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
            components = self._data['stack'][l]['levels'][s]['alignment_history'][method]['method_results']['snr']
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
        # logger.critical(f"[{caller}]")
        #Todo called too frequently by snr_errorbar_size
        try:
            method = self.method(s=s, l=l)
            return self._data['stack'][l]['levels'][s]['alignment_history'][method]['method_results']['snr_report']
        except:
            logger.warning('No SNR Report for Layer %d' % l)
            return ''


    def snr_errorbar_size(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            if l == 0:
                return 0.0
            report = self.snr_report(s=s, l=l)
            if not isinstance(report, str):
                logger.debug(f'No SNR Report Available For Layer {l}, Returning 0.0...')
                return 0.0
            substr = '+-'
            return float(report[report.index(substr) + 2: report.index(substr) + 5])
        except:
            return 0.0


    def snr_errorbars(self, s=None):
        '''Note Length Of Return Array has size self.n_sections() - 1 (!)'''
        if s == None: s = self.level
        return np.array([self.snr_errorbar_size(s=s, l=l) for l in range(0, len(self))])


    def check_snr_status(self, s=None) -> list:
        if s == None: s = self.level
        unavailable = []
        for i,l in enumerate(self.stack(s=s)):
            if not 'snr' in l['method_results']:
                unavailable.append((i, self.name_base(s=s, l=i)))
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


    def method(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['swim_settings']['method']
        except:
            print_exception(extra=f"Section #{l}")

    def method_pretty(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        convert = {'grid_default': 'Grid Align', 'grid_custom': 'Grid Custom',
                   'manual_strict': 'Manual Strict', 'manual_hint': 'Manual Hint'}
        return convert[self._data['stack'][l]['levels'][s]['swim_settings']['method']]


    def set_all_methods_automatic(self):
        '''Sets the alignment method of all sections and all scales to Auto-SWIM.'''
        for l in range(len(self)):
            self._data['stack'][l]['levels'][self.level]['swim_settings']['method'] = 'grid_default'

        self.set_manual_swim_windows_to_default()

    def manpoints(self, s=None, l=None):
        '''Returns manual correspondence points in Neuroglancer format'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['manual']['points']['ng_coords']

    def set_manpoints(self, role, matchpoints, l=None):
        '''Sets manual correspondence points for a single section at the current level, and applies
         scaling factor then sets the same points for all scale levels above the current level.'''
        if l == None: l = self.zpos
        logger.info(f"Writing manual points to project dictionary for section #{l}: {matchpoints}")
        # lvls  = [x for x in self.lvls() if x <= self.lvl()]
        # scales      = [get_scale_key(x) for x in lvls]
        glob_coords = [None,None,None]
        fac = self.lvl()
        for i,p in enumerate(matchpoints):
            if p:
                glob_coords[i] = (p[0] * fac, p[1] * fac)

        for s in self.finer_scales():
            # set manual points in Neuroglancer coordinate system
            fac = self.lvl(s)
            coords = [None,None,None]
            for i,p in enumerate(glob_coords):
                if p:
                    coords[i] = (p[0] / fac, p[1] / fac)
            logger.info(f'Setting manual points for {s}: {coords}')
            # self._data['stack'][z]['levels'][level]['swim_settings']['match_points'][role] = coords
            self._data['stack'][l]['levels'][s]['swim_settings']['manual']['points']['ng_coords'][role] = coords

            # set manual points in MIR coordinate system
            img_width = self.image_size(s=s)[0]
            mir_coords = [None,None,None]
            for i,p in enumerate(coords):
                if p:
                    mir_coords[i] = [img_width - p[1], p[0]]
            self._data['stack'][l]['levels'][s]['swim_settings']['manual']['points']['mir_coords'][role] = mir_coords

    def manpoints_mir(self, role, s=None, l=None):
        '''Returns manual correspondence points in MIR format'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['manual']['points']['mir_coords'][role]

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
            r = sec['swim_settings']['manual']['points']['ng_coords']['ref']
            b = sec['swim_settings']['manual']['points']['ng_coords']['tra']
            if r != []:
                logger.info(f'Index: {i}, Ref, Match Points: {str(r)}')
            if b != []:
                logger.info(f'Index: {i}, Base, Match Points: {str(b)}')


    def getmpFlat(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        mps = self['stack'][l]['levels'][s]['swim_settings']['manual']['points']['ng_coords']
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
            return self._data['stack'][l]['levels'][s]['alignment_history'][method]['method_results'][
            'affine_matrix']
        except:
            print_exception()
            return [[[1, 0, 0], [0, 1, 0]]]

    #0802+
    def swim_settings_hashable(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        # return [tuple(map(tuple, x)) for x in self.cafm_list(level=level,end=end)]
        # return hash(str(self.cafm_list(level=level,end=end)))
        try:
            return hash(str(self['stack'][l]['levels'][s]['swim_settings']))
        except:
            print_exception(extra=f'level={s}, l={l}')


    def cafm(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            # return self._data['stack'][z]['levels'][level]['alignment']['method_results']['cumulative_afm'] #0802-
            method = self.method(s=s, l=l)
            return self._data['stack'][l]['levels'][s]['alignment_history'][method]['method_results']['cumulative_afm']
        except:
            # caller = inspect.stack()[1].function
            # print_exception(extra=f'Layer {z}, caller: {caller}')
            exi = sys.exc_info()
            logger.warning(f"[{l}] {exi[0]} {exi[1]}")
            return [[1, 0, 0], [0, 1, 0]]


    def afm_list(self, s=None, l=None) -> list:
        if s == None: s = self.level
        lst = [self.afm(l=i) for i, l in enumerate(self.stack(s=s))]
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


    def cafm_hashable(self, s=None, end=None):
        if s == None: s = self.level
        if end == None: end = self.zpos
        # return [tuple(map(tuple, x)) for x in self.cafm_list(level=level,end=end)]
        # return hash(str(self.cafm_list(level=level,end=end)))
        try:
            # return hash(str(self.cafm(level=level, z=end)))
            return hashstring(str(self.cafm(s=s, l=end)))
        except:
            caller = inspect.stack()[1].function
            print_exception(extra=f'end={end}, caller: {caller}')


    def cafm_registered_hash(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self['stack'][l]['levels'][s]['cafm_hash']


    def cafm_current_hash(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        # return hash(str(self.cafm_list(level=level, end=z)))
        try:
            return self.cafm_hashable(s=s, end=l)
        except:
            print_exception(extra=f"scale={s}, section={l}")

    #Deprecated now registering cafm hash in SetStackCafm
    def register_cafm_hashes(self, indexes, s=None):
        logger.info('Registering cafm hashes...')
        if s == None: s = self.level
        for i in indexes:
            self['stack'][i]['levels'][s]['cafm_hash'] = self.cafm_current_hash(l=i)


    def cafm_hash_comports(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        answer = self.cafm_registered_hash(s=s, l=l) == self.cafm_current_hash(s=s, l=l)
        self['stack'][l]['levels'][s]['cafm_comports'] = answer
        return answer


    def isdefaults(self, level=None, z=None):
        logger.critical('')
        if level == None: level = self.level
        if z == None: z = self.zpos
        caller = inspect.stack()[1].function
        # logger.critical(f"caller: {caller}, level={level}, z={z}")
        reasons = []
        method = self.method(s=level, l=z)

        cur = self['stack'][z]['levels'][level]['swim_settings']  # current
        dflts = self['defaults'][level]  # memory

        if method in ('manual_hint', 'manual_strict'):
            reasons.append((f"Uses manual alignment rather than default grid alignment", cur['method'], dflts['method']))
            answer = len(reasons) == 0
            return answer, reasons

        #Todo figure this out later
        # if cur['reference'] != dflts['reference']:
        #     reasons.append(('Reference images differ', cur['reference'], dflts['reference']))

        if cur['clobber_fixed_noise'] != dflts['clobber_fixed_noise']:
            reasons.append(("Inconsistent data at clobber fixed pattern ON/OFF (key: clobber_fixed_noise)",
                             cur['clobber_fixed_noise'],
                             dflts['clobber_fixed_noise']))
        elif (cur['clobber_fixed_noise'] == True) and (dflts['clobber_fixed_noise'] == True):
            if cur['clobber_size'] != dflts['clobber_size']:
                reasons.append(("Inconsistent data at clobber size in pixels (key: clobber_size)",
                                 cur['clobber_size'], dflts['clobber_size']))

        else:
            if cur['whitening'] != dflts['whitening']:
                reasons.append(("Inconsistent data at signal whitening magnitude (key: whitening)",
                                 cur['whitening'], dflts['whitening']))
            if cur['iterations'] != dflts['iterations']:
                reasons.append(("Inconsistent data at # SWIM iterations (key: swim_iters)",
                                 cur['iterations'], dflts['iterations']))

        if 'grid' in method:
            keys = ['size_1x1', 'size_2x2', 'quadrants']
            for key in keys:
                if cur['grid'][key] != dflts['grid'][key]:
                    reasons.append((f"Inconsistent data (key: {key})", cur['grid'][key], dflts['grid'][key]))


        answer = len(reasons) == 0
        logger.critical(f"Returning {answer}!\nReasons: {reasons}")
        return answer, reasons



    def data_comports(self, level=None, z=None):
        if level == None: level = self.level
        if z == None: z = self.zpos
        caller = inspect.stack()[1].function
        # logger.critical(f"caller: {caller}, level={level}, z={z}")
        problems = []
        method = self.method(s=level, l=z)

        #Temporary
        if z == self.first_unskipped():
            return True, []

        if not self['stack'][z]['levels'][level]['alignment_history'][method]['complete']:
            problems.append((f"Alignment method '{method}' is incomplete", 1, 0))
            return False, problems

        cur = self['stack'][z]['levels'][level]['swim_settings']  # current
        mem = self['stack'][z]['levels'][level]['alignment_history'][method]['swim_settings'] # memory

        #Todo refactor, 'recent_method' key
        try:
            last_method_used = self['stack'][z]['levels'][level]['method_results']['method']
            if last_method_used != cur['method']:
                problems.append(('Method changed', last_method_used, cur['method']))
        except:
            pass

        if cur['reference'] != mem['reference']:
            problems.append(('Reference images differ', cur['reference'], mem['reference']))

        if cur['clobber_fixed_noise'] != mem['clobber_fixed_noise']:
            problems.append(("Inconsistent data at clobber fixed pattern ON/OFF (key: clobber_fixed_noise)", cur['clobber_fixed_noise'],
                             mem['clobber_fixed_noise']))
        if cur['clobber_fixed_noise']:
            if cur['clobber_size'] != mem['clobber_size']:
                problems.append(("Inconsistent data at clobber size in pixels (key: clobber_size)",
                                 cur['clobber_size'], mem['clobber_size']))

        # if method == 'grid_default':
        #     for key in self.defaults:
        #         if key in mem['defaults']:
        #             if key in ('bounding_box', 'polynomial_bias'):
        #                 continue
        #             if self.defaults[key] != mem['defaults'][key]:
        #                 if type(mem['defaults'][key]) == dict and len(mem['defaults'][key]) == 1:
        #                     breadcrumb = 'defaults > %level > %level' % (key, mem['defaults'][key])
        #                 else:
        #                     breadcrumb = 'defaults > %level' % key
        #                 problems.append(('Inconsistent data (key: %level)' % breadcrumb,
        #                                  self.defaults[key], mem['defaults'][key]))

        else:
            if cur['whitening'] != mem['whitening']:
                problems.append(("Inconsistent data at signal whitening magnitude (key: whitening)",
                                 cur['whitening'], mem['whitening']))
            if cur['iterations'] != mem['iterations']:
                problems.append(("Inconsistent data at # SWIM iterations (key: swim_iters)",
                                 cur['iterations'], mem['iterations']))

        if 'grid' in method:
            keys = ['size_1x1', 'size_2x2', 'quadrants']
            for key in keys:
                if cur['grid'][key] != mem['grid'][key]:
                    problems.append((f"Inconsistent data (key: {key})", cur['grid'][key], mem['grid'][key]))

        if method in ('manual_hint', 'manual_strict'):
            if cur['manual']['points']['mir_coords'] != mem['manual']['points']['mir_coords']:
                problems.append((f"Inconsistent match points",
                                 cur['manual']['points']['mir_coords'], mem['manual']['points']['mir_coords']))

            if method == 'manual_hint':
                if cur['manual']['size_region'] != mem['manual']['size_region']:
                    problems.append((f"Inconsistent match region size (key: manual_swim_window_px)",
                                     cur['manual']['size_region'], mem['manual']['size_region']))
        # elif method == 'grid-custom':
        #     return cur['defaults'] == mem['defaults']
        answer = len(problems) == 0
        self['stack'][z]['levels'][level]['data_comports'] = answer
        return answer, problems
        # return tuple(comports?, [(reason/key, val1, val2)])

    def updateComportsKeys(self, one=False, forward=False, all=False, indexes=None):
        logger.critical(f"[{caller_name()}] Updating Comports Keys...")
        if one:        to_update = range(self.zpos, self.zpos+1)
        elif forward:  to_update = range(self.zpos, len(self))
        elif indexes:  to_update = indexes
        elif all:      to_update = range(0, len(self))
        else:          to_update = range(self.zpos, self.zpos+1)
        for i in to_update:
            _data_comports = self['stack'][i]['levels'][self.level]['data_comports']
            _cafm_comports = self['stack'][i]['levels'][self.level]['cafm_comports']
            data_comports = self.data_comports(level=self.level, z=i)[0]
            cafm_comports = self.cafm_hash_comports(s=self.level, l=i)
            if _data_comports != data_comports:
                logger.critical(f"Changing 'data_comports' from {_data_comports} to {data_comports} for section #{i}")
            if _cafm_comports != cafm_comports:
                logger.critical(f"Changing 'data_comports' from {_cafm_comports} to {cafm_comports} for section #{i}")
            self['stack'][i]['levels'][self.level]['data_comports'] = data_comports
            self['stack'][i]['levels'][self.level]['cafm_comports'] = cafm_comports


    def data_comports_list(self, s=None):
        if s == None: s = self.level
        # return np.array([self.data_comports(level=level, z=z)[0] for z in range(0, len(self))]).nonzero()[0].tolist()
        return [self['stack'][i]['levels'][s]['data_comports'] for i in range(0,len(self))]


    def data_dn_comport_indexes(self, s=None):
        if s == None: s = self.level
        t0 = time.time()
        # lst = [(not self.data_comports(level=level, z=z)[0]) and (not self.skipped(level=level, z=z)) for z in range(0, len(self))]
        # answer = np.array(lst).nonzero()[0].tolist()
        answer = []
        for i in range(0, len(self)):
            if self.include(s=s, l=i):
                if not self['stack'][i]['levels'][s]['data_comports']:
                    answer.append(i)
        t1 = time.time()
        logger.info(f"dt = {time.time() - t0:.3g} ({t1 - t0:.3g}/{time.time() - t1:.3g})")
        return answer


    def all_comports_indexes(self, s=None):
        if s == None: s = self.level
        t0 = time.time()
        answer = []
        for i in range(len(self)):
            if self['stack'][i]['levels'][s]['data_comports']:
                if self['stack'][i]['levels'][s]['cafm_comports']:
                    answer.append(i)
        # answer = list(set(range(len(self))) - set(self.cafm_dn_comport_indexes(level=level)) - set(self.data_dn_comport_indexes(
        #     level=level)))
        logger.info(f"dt = {time.time() - t0:.3g}")
        return answer


    def cafm_comports_indexes(self, s=None):
        if s == None: s = self.level
        # return np.array([self.cafm_hash_comports(level=level, z=z) for z in range(0, len(self))]).nonzero()[0].tolist()
        answer = []
        for i in range(len(self)):
            if self['stack'][i]['levels'][s]['cafm_comports']:
                answer.append(i)
        return answer


    def cafm_dn_comport_indexes(self, s=None):
        if s == None: s = self.level
        t0 = time.time()
        answer = []
        for i in range(len(self)):
            if self.include(s=s, l=i):
                if (not self['stack'][i]['levels'][s]['data_comports']) or (not self['stack'][i]['levels'][s]['cafm_comports']):
                    answer.append(i)
        logger.info(f"dt = {time.time() - t0:.3g}")
        return answer




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


    def skips_list(self, s=None) -> list:
        '''Returns the list of excluded images for a level'''
        if s == None: s = self.level
        indexes, names = [], []
        try:
            for i in range(0,len(self)):
                if not self['stack'][i]['levels'][s]['swim_settings']['include']:
                    indexes.append(i)
                    names.append(os.path.basename(self['stack'][i]['levels'][s]['swim_settings']['path']))
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
        for level in self.finer_scales():
            self._data['stack'][l]['levels'][level]['swim_settings']['iterations'] = val
        self.signals.warning2.emit()


    def swim_settings(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']


    def set_whitening(self, f: float) -> None:
        '''Sets the Whitening Factor for the Current Layer.'''
        for level in self.finer_scales():
            self._data['stack'][self.zpos]['levels'][level]['swim_settings']['whitening'] = f
        self.signals.warning2.emit()


    def swim_1x1_custom_px(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        # return self.stack()[self.zpos]['swim_settings']]['grid-custom-px']
        return tuple(self._data['stack'][l]['levels'][s]['swim_settings']['grid']['size_1x1'])

    def set_swim_1x1_custom_px(self, pixels=None, silent=False):
        '''Sets the SWIM Window for the Current Section across all scales.'''
        # if pixels == None:
        #     self.set_auto_swim_windows_to_default(current_only=True)
        if (pixels % 2) == 1:
            pixels -= 1
            if int(pixels/2) % 2 == 1:
                pixels -= 2
        img_w, img_h = self.image_size(s=self.level)
        pixels = pixels
        pixels_y = (pixels / img_w) * img_h
        self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['grid']['size_1x1'] = [pixels,pixels_y]
        if (self.swim_2x2_custom_px()[0] * 2) > pixels:
            self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['grid']['size_2x2'] = [int(pixels / 2  + 0.5), int(pixels_y / 2 + 0.5)]
        if not silent:
            self.signals.warning2.emit()



    def propagate_swim_1x1_custom_px(self, indexes:list):
        '''Sets the SWIM Window for the Current Section across all scales.'''
        # img_w, img_h = self.image_size(level=self.level)
        # logger.critical(f"caller: {caller_name()}")
        for l in indexes:
            pixels = self._data['stack'][l]['levels'][self.level]['swim_settings']['grid']['size_1x1']
            for s in self.finer_scales():
                sf = self.lvl() / self.lvl(s)
                self._data['stack'][l]['levels'][s]['swim_settings']['grid']['size_1x1'] = [int(pixels[0] * sf + 0.5), int(pixels[1] * sf + 0.5)]


    def swim_2x2_custom_px(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return tuple(self._data['stack'][l]['levels'][s]['swim_settings']['grid']['size_2x2'])


    def set_swim_2x2_custom_px(self, pixels=None, silent=False):
        '''Returns the SWIM Window in pixels'''
        caller = inspect.stack()[1].function
        # if pixels == None:
        #     self.set_auto_swim_windows_to_default(current_only=True)
        if (pixels % 2) == 1:
            pixels -= 1

        img_w, img_h = self.image_size(s=self.level)
        pixels_y = (pixels / img_w) * img_h

        if (2 * pixels) <= self.swim_1x1_custom_px()[0]:
            self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['grid']['size_2x2'] = [pixels,
                                                                                                        pixels_y]
        else:
            force_pixels = [int(self.swim_1x1_custom_px()[0] / 2 + 0.5),int(self.swim_1x1_custom_px()[1] / 2 + 0.5)]
            if (force_pixels[0] % 2) == 1:
                force_pixels[0] -= 1
                force_pixels[1] -= 1
            self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']['grid']['size_2x2']\
             = \
                force_pixels
        if not silent:
            self.signals.warning2.emit()


    def propagate_swim_2x2_custom_px(self, indexes:list):
        '''Returns the SWIM Window in pixels'''
        # img_w, img_h = self.image_size(level=self.level)
        for l in indexes:
            pixels = self._data['stack'][l]['levels'][self.level]['swim_settings']['grid']['size_2x2']
            for s in self.finer_scales(include_self=False):
                sf = self.lvl() / self.lvl(s)  # level factor
                self._data['stack'][l]['levels'][s]['swim_settings']['grid']['size_2x2'] = [int(pixels[0]*
                                                                                                        sf+ 0.5),
                                                                                              int(pixels[1] * sf + 0.5)]


    #Todo 0612
    def set_auto_swim_windows_to_default(self, levels=None, factor=None, current_only=False, silent=False) -> None:

        if levels == None:
            levels = self.finer_scales()

        img_size = self.image_size(self.levels[0])  # largest level size
        # man_ww_full = min(img_size[0], img_size[1]) * cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC
        if factor == None:
            factor = cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC
        man_ww_full = img_size[0] * factor, img_size[1] * factor
        # for level in self.levels():
        for s in levels:
            man_ww_x = int(man_ww_full[0] / self.lvl(s) + 0.5)
            man_ww_y = int(man_ww_full[1] / self.lvl(s) + 0.5)

            if current_only:
                self['stack'][self.zpos]['levels'][s]['swim_settings']['grid']['size_1x1'] = [int(man_ww_x),int(man_ww_y)]
                self['stack'][self.zpos]['levels'][s]['swim_settings']['grid']['size_2x2'] = [int(man_ww_x / 2 + 0.5), int(man_ww_y / 2 + 0.5)]
            else:
                self['defaults'][s]['window_size'] = [man_ww_x, man_ww_y]
                for i in range(len(self)):
                    self['stack'][i]['levels'][s]['swim_settings']['grid']['size_1x1'] = [int(man_ww_x),
                                                                                            int(man_ww_y)]
                    self['stack'][i]['levels'][s]['swim_settings']['grid']['size_2x2'] = [int(man_ww_x / 2 +
                                                                                                     0.5),
                                                                                            int(man_ww_y/ 2 + 0.5)]
        if not silent:
            self.signals.warning2.emit()

    def manual_swim_window_px(self, s=None, l=None) -> int:
        '''Returns the SWIM Window for the Current Layer.'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return int(self['stack'][l]['levels'][s]['swim_settings']['manual']['size_region'])

    def set_manual_swim_window_px(self, pixels=None, silent=False) -> None:
        '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
        logger.info(f'Setting Local SWIM Window to [{pixels}] pixels...')

        if (pixels % 2) == 1:
            pixels -= 1

        self['stack'][self.zpos]['levels'][self.level]['swim_settings']['manual']['size_region'] = pixels
        if not silent:
            self.signals.warning2.emit()


    def propagate_manual_swim_window_px(self, indexes) -> None:
        '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
        # logger.info('Propagating swim regions to finer scales...')
        for l in indexes:
            pixels = self['stack'][l]['levels'][self.level]['swim_settings']['manual']['size_region']
            for s in self.finer_scales():
                sf = self.lvl() / self.lvl(s)  # level factor
                self['stack'][l]['levels'][s]['swim_settings']['manual']['size_region'] = int(pixels * sf + 0.5)
                #todo
                # self['stack'][z]['levels'][level]['swim_settings']['manual']['size_region'] = (
                #             np.array(pixels) * sf).astype(int).tolist()

    def set_manual_swim_windows_to_default(self, levels=None, current_only=False, silent=False) -> None:
        logger.info('')
        if levels == None:
            levels = self.finer_scales()

        img_size = self.image_size(self.levels[0])  # largest level size
        man_ww_full = min(img_size[0], img_size[1]) * cfg.DEFAULT_MANUAL_SWIM_WINDOW_PERC
        # for level in self.levels():
        for s in levels:
            man_ww = man_ww_full / self.lvl(s)['manual']
            # logger.info(f'Manual SWIM window size for {level} to {man_ww}')
            if current_only:
                self['stack'][self.zpos]['levels'][s]['swim_settings']['manual']['size_region'] = man_ww
            else:
                for i in range(len(self)):
                    self['stack'][i]['levels'][s]['swim_settings']['manual']['size_region'] = man_ww
        if not silent:
            self.signals.warning2.emit()

    def image_size(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['series']['size_xy'][s])

    def size_xy(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['series']['size_xy'][s])

    def size_zyx(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['series']['size_zyx'][s])


    def name_base(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['path'])
        except:
            return ''


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
        '''Returns the Use Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.level
        return bool(self['level_data'][s]['output_settings']['bounding_box']['use'])

    def set_use_bounding_rect(self, b: bool, s=None) -> None:
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
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
        if s == None: s = self.level
        for section in self.get_iter(s=s):
            if section['levels'][self.level]['swim_settings']['include']:
                return section['levels'][self.level]['swim_settings']['index']


    def link_reference_sections(self, levels=None):
        logger.critical('Linking reference sections...')
        if levels == None:
            levels = self.finer_scales()
        for s in levels:
            skip_list = self.skips_indices(s=s)
            for layer_index in range(len(self)):
                j = layer_index - 1  # Find nearest previous non-skipped z
                while (j in skip_list) and (j >= 0):
                    j -= 1
                if (j not in skip_list) and (j >= 0):
                    ref = self['stack'][j]['levels'][s]['swim_settings']['path']
                    self['stack'][layer_index]['levels'][s]['swim_settings']['reference'] = ref
            self['stack'][self.first_unskipped(s=s)]['levels'][s]['swim_settings']['reference'] = ''  # 0804
        logger.info("<<")

        def link_full_resolution(self):
            t0 = time.time()
            logger.info('Symbolically linking full scale images >>>>')
            for img in self.basefilenames():
                fn = os.path.join(self.source_path, img)
                ofn = os.path.join(self.location, 'tiff', 's1', os.path.split(fn)[1])
                # normalize path for different OSs
                if os.path.abspath(os.path.normpath(fn)) != os.path.abspath(os.path.normpath(ofn)):
                    try:
                        os.unlink(ofn)
                    except:
                        pass
                    try:
                        os.symlink(fn, ofn)
                    except:
                        logger.warning("Unable to link %s to %s. Copying instead." % (fn, ofn))
                        try:
                            shutil.copy(fn, ofn)
                        except:
                            logger.warning("Unable to link or copy from " + fn + " to " + ofn)
            dt = time.time() - t0
            logger.info(f'<<<< {dt}')

    def applyPresetDefaults(self, levels=None, finer_only=False, update_current=False):
        if finer_only:
            levels=self.finer_scales()
        elif not levels:
            levels = self.levels

        logger.critical(f"Applying preset defaults to levels {', '.join(levels)} (Update current? {update_current})")

        presets = self.gatherDataPresets()
        self._data['preset_defaults'] = copy.deepcopy(presets)

        self._data['defaults'].update(presets)
        for level in levels:
            # d = self._data['defaults'][level]
            # d.update(presets[level])

            if update_current:
                for i in range(self.count):
                    for level in levels:
                        self['stack'][i]['levels'][level]['swim_settings'].update(presets[level])


    def getDataPresets(self):
        return self['preset_defaults']


    def applyLevelDefaults(self):
        for level in self.finer_scales():
            self['stack'][self.zpos]['levels'][self.level]['swim_settings'].update(copy.deepcopy(self.defaults))
        self.signals.warning2.emit()


    def gatherDataPresets(self) -> dict:
        logger.info("Getting data presets...")

        fullsize = np.array(self['series']['size_xy'][self.levels[0]], dtype=int)
        s1_size_1x1 = fullsize * cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC
        s1_region_size = (fullsize * cfg.DEFAULT_MANUAL_SWIM_WINDOW_PERC)

        d_ww = {v: {} for v in self.levels}
        for lev in self.levels:
            factor = int(lev[1:])
            _1x1 = np.rint(s1_size_1x1 / factor).astype(int).tolist()
            _2x2 = np.rint(s1_size_1x1 / factor / 2).astype(int).tolist()
            _regions = np.rint(s1_region_size / factor).astype(int).tolist()[0]
            # Temporary ^. Take first value only. This should perhaps be rectangular, two-value.
            _1x1 = ensure_even(_1x1, extra='1x1 size')
            _2x2 = ensure_even(_2x2, extra='2x2 size')
            _regions = ensure_even(_regions, extra='region size')
            d_ww[lev]['size_1x1'] = _1x1
            d_ww[lev]['size_2x2'] = _2x2
            d_ww[lev]['size_region'] = _regions

        d = {v: {} for v in self.levels}
        for k, v in d.items():
            logger.critical(f"k = {k}")
            v.update(
                method=cfg.DEFAULT_METHOD,
                clobber_fixed_noise=cfg.DEFAULT_USE_CLOBBER,
                clobber_size=cfg.DEFAULT_CLOBBER_PX,
                iterations=cfg.DEFAULT_SWIM_ITERATIONS,
                whitening=cfg.DEFAULT_WHITENING,
                initial_rotation=cfg.DEFAULT_INITIAL_ROTATION,
                grid={
                    'size_1x1': copy.deepcopy(d_ww[k]['size_1x1']),
                    'size_2x2': copy.deepcopy(d_ww[k]['size_2x2']),
                    'quadrants': [1] * 4,
                },
                manual={
                    'size_region': copy.deepcopy(d_ww[k]['size_region']),
                    'points': {
                        'ng_coords': {
                            'tra': (None, None, None),
                            'ref': (None, None, None)
                        },
                        'mir_coords': {
                            'tra': (None, None, None),
                            'ref': (None, None, None)
                        }
                    }
                }
            )

        logger.info(f"Presets :\n{str(d)}\n")
        return d


    def initializeStack(self, series_info, location=location):
        logger.critical(f"\n\nInitializing data model ({location})...\n")

        levels = natural_sort(series_info['levels'])
        paths = natural_sort(series_info['paths'])

        self._data.update(
            info={
                'location': location,
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
                'level': natural_sort(series_info['levels'])[-1],
                'z_position': 0
            },
            defaults={s: {} for s in levels},
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
            }
        )

        for i in range(self.count):
            basename = os.path.basename(paths[i])
            self['stack'].append({})
            self['stack'][i].update(
                index=i,
                name=basename,
                path=paths[i],
                levels={s: {} for s in levels},
                notes=''
            )
            for level in levels:
                path = os.path.join(series_info['location'], 'tiff', level, basename)
                self['stack'][i]['levels'][level].update(
                    data_comports=True,
                    cafm_comports=True,
                    cafm_hash=None,
                    method_results={
                        'snr': 0.0,
                        'snr_report': 'SNR: --',
                        'cumulative_afm': None,
                        'affine_matrix': [[1., 0., 0.], [0., 1., 0.]]
                    },
                    swim_settings={
                        'index': i,
                        'path': path,
                        'reference': None,
                        'include': True,
                        'level': level
                    },
                    alignment_history={v: {
                        # 'swim_settings': None,
                        'method_results': {
                            'snr': 0.0,
                            'snr_report': 'SNR: --',
                            'cumulative_afm': None,
                            'affine_matrix': [[1., 0., 0.], [0., 1., 0.]]
                        },
                        'complete': False
                    } for v in cfg.ALIGNMENT_METHODS}

                )

        for level in levels:
            self['level_data'][level].update(
                initial_snr=None,
                aligned=False,
                output_settings={
                    'bounding_box': {
                        'use': False,
                        'has': False,
                        'size': None,
                    },
                    'polynomial_bias': cfg.DEFAULT_CORRECTIVE_POLYNOMIAL
                }
            )
        self.applyPresetDefaults(update_current=True)
        self.link_reference_sections(levels)
        '''deprecated keys: grid_custom_px_1x1, grid_custom_px_2x2, grid_custom_regions'''


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
    if isinstance(vals, int):
        #integer
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
            try:
                assert x % 2 == 0
            except:
                msg = f"Odd window size: {x}. Adding one pixel to keep things even for SWIM."
                if extra: msg = f'[{extra}] ' + msg
                logger.warning(msg)
                vals[i] += 1
                logger.info(f"Modified: {vals[i]}")
    return vals



if __name__ == '__main__':
    data = DataModel()
    print('Data Model Version: ' + str(data['version']))
    print(data)
