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


from src.data_structs import data_template, layer_template
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


class DataModel:

    """ Encapsulate datamodel dictionary and wrap with methods for convenience """
    def __init__(self, data=None, name=None, location=None, quietly=False, mendenhall=False):
        self._current_version = cfg.VERSION
        if not quietly:
            logger.info(f"Initializing DataModel '{name}'...")
        if data:
            self._data = data  # Load project data from file
        else:
            self._data = copy.deepcopy(data_template)  # Initialize new project data
            self._data['created'] = date_time()
            self.set_system_info()
        if not quietly:
            self._data['modified'] = date_time()
            self.signals = Signals()
            self.signals.zposChanged.connect(cfg.mw._updateZposWidgets)
        self._data['data']['mendenhall'] = mendenhall
        self._data['version'] = cfg.VERSION
        if name:
            self.name = name

        if location:
            self.location = location

        self._data.setdefault('changelog', [])

        # self.zpos = self._data['data']['z_position']
        if not quietly:
            logger.info('<<<< __init__ <<<<')

    def __iter__(self):
        for item in self['stack'][self.zpos]['levels'][self.scale]:
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
    def name(self) -> str:
        return self['name']


    @name.setter
    def name(self, v):
        self['name'] = v

    @property
    def created(self):
        return self._data['created']

    @created.setter
    def created(self, val):
        self._data['created'] = val


    @property
    def location(self):
        return self['location']

    @location.setter
    def location(self, p):
        self['location'] = p

    @property
    def scales(self) -> list[str]:
        '''Return list of scale level keys.'''
        return natural_sort(self['series']['scale_keys'])

    @property
    def source_path(self):
        return self['source_path']

    @source_path.setter
    def source_path(self, p):
        self['source_path'] = p


    # def created(self):
    #     return self._data['created']

    #Todo set this independently from 'modified', 'modified' should update only when saved

    @property
    def last_opened(self):
        return self._data['modified']

    @last_opened.setter
    def last_opened(self, val):
        self._data['modified'] = val

    @property
    def modified(self):
        return self._data['modified']

    @modified.setter
    def modified(self, val):
        self._data['modified'] = val

    @property
    def zpos(self):
        '''Returns the Current Layer as an Integer.'''
        return self['data']['z_position']

    @zpos.setter
    def zpos(self, index):
        caller = inspect.stack()[1].function
        # self._data['data']['Current Section (Index)'] = index
        if int(index) in range(0, len(self)):
            if int(index) != self.zpos:
                self['data']['z_position'] = int(index)
                logger.info(f"[{index}] Z-position Changed!")
                self.signals.zposChanged.emit()
                QApplication.processEvents()
        else:
            logger.warning(f'\n\nINDEX OUT OF RANGE: {index} [caller: {inspect.stack()[1].function}]\n')

    @property
    def cname(self) -> str:
        '''Returns the default Zarr cname/compression type as a string.'''
        return self['series']['settings']['cname']

    @cname.setter
    def cname(self, x:str):
        self['series']['settings']['cname'] = str(x)

    @property
    def clevel(self) -> int:
        '''Returns the default Zarr clevel/compression level as an integer.'''
        return int(self['series']['settings']['clevel'])

    @clevel.setter
    def clevel(self, x:int):
        self['series']['settings']['clevel'] = int(x)

    @property
    def chunkshape(self) -> tuple:
        '''Returns the  default chunk shape tuple.'''
        return self['series']['settings']['chunkshape']

    @chunkshape.setter
    def chunkshape(self, x:tuple):
        self['series']['settings']['chunkshape'] = x

    @property
    def brightness(self):
        return self['rendering']['brightness']

    @brightness.setter
    def brightness(self, val):
        self['rendering']['brightness'] = val

    @property
    def contrast(self):
        return self['rendering']['contrast']

    @contrast.setter
    def contrast(self, val):
        self['rendering']['contrast'] = val

    @property
    def scale_key(self):
        return self['data']['current_scale']

    @scale_key.setter
    def scale_key(self, str):
        self['data']['current_scale'] = str

    @property
    def scale(self):
        return self['data']['current_scale']

    @scale.setter
    def scale(self, str):
        self['data']['current_scale'] = str

    @property
    def series(self):
        '''Returns the original series info for the alignment'''
        return self['series']

    @property
    def current_method(self):
        try:
            return self['stack'][self.zpos]['levels'][self.scale]['swim_settings']['method']
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
            'grid-default': 'Grid Default',
            'grid-custom': 'Grid Custom',
            'manual-hint': 'Correspondence Points, Hint',
            'manual-strict': 'Correspondence Points, Strict'
        }
        return convert[self.current_method]

    @property
    def grid_custom_regions(self):
        return self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings']['grid_custom_regions']

    @grid_custom_regions.setter
    def grid_custom_regions(self, lst):
        # for s in self.scales():
        for s in self.finer_scales():
            self._data['stack'][self.zpos]['levels'][s]['swim_settings']['grid_custom_regions'] = lst
        self.signals.warning2.emit()

    def get_grid_custom_regions(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings'][
            'grid_custom_regions']


    @property
    def default_poly_order(self):
        return self._data['defaults']['corrective-polynomial']

    @default_poly_order.setter
    def default_poly_order(self, use):
        self._data['defaults']['corrective-polynomial'] = use
        self.signals.warning2.emit()


    @property
    def default_whitening(self):
        return self._data['defaults']['signal-whitening']

    @default_whitening.setter
    def default_whitening(self, x):
        self._data['defaults']['signal-whitening'] = x
        self.signals.warning2.emit()

    @property
    def defaults(self):
        return self._data['defaults']

    @defaults.setter
    def defaults(self, d):
        self._data['defaults'] = d

    @property
    def defaults_pretty(self):
        d = self._data['defaults']
        defaults_str = ''
        nl = '\n'
        defaults_str += f"Bounding Box: {d['bounding-box']}\n" \
                        f"Corrective Polynomial: {d['corrective-polynomial']}\n" \
                        f"Initial Rotation: {d['initial-rotation']}\n" \
                        f"SWIM Window Dimensions:\n{nl.join(['  %s: %s' % (s.ljust(9), '%sx%s' % tuple(d[s]['swim-window-px'])) for s in self.scales])}\n" \
                        f"SWIM iterations: {d['swim-iterations']}\n" \
                        f"SWIM Signal Whitening: {d['signal-whitening']}"
        return defaults_str

    # layer['swim_settings']].setdefault('karg', False)

    @property
    def count(self):
        return len(self)

    def section(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]


    # def set_fullscale_settings(self):


    def get_ref_index(self, l=None):
        if l == None: l = self.zpos
        caller = inspect.stack()[1].function
        # logger.critical(f'caller: {caller}, l={l}')
        # if self.skipped(s=self.scale, l=l):
        if not self.include(s=self.scale, l=l):
            return self.get_index(self._data['stack'][l]['levels'][self.scale]['filename']) #Todo refactor this but not sure how
        reference = self._data['stack'][l]['levels'][self.scale]['swim_settings']['reference']
        if reference == '':
            return self.get_index(self._data['stack'][l]['levels'][self.scale]['filename'])
        else:
            return self.get_index(reference)

    # @cache
    def is_aligned(self, s=None):
        if s == None: s = self.scale
        return self['alignment_status'][s]



    def is_alignable(self) -> bool:
        '''Checks if the current scale is able to be aligned'''
        try:
            scales_list = self.scales
            cur_scale_key = self.scale
            coarsest_scale = scales_list[-1]
            if cur_scale_key == coarsest_scale:
                # logger.info("is cur scale_key alignable? returning True")
                return True
            cur_scale_index = scales_list.index(cur_scale_key)
            next_coarsest_scale_key = scales_list[cur_scale_index + 1]
            if not self.is_aligned(s=next_coarsest_scale_key):
                return False
            else:
                return True
        except:
            print_exception()

    def is_aligned_and_generated(self, s=None) -> bool:
        if s == None: s = self.scale
        #Todo improve this, cache it or something

        # if s in get_scales_with_generated_alignments(self.scales):
        #     return True
        # else:
        #     return False
        try:
            if len(os.listdir(os.path.join(self.dest(), 'img_aligned.zarr', 's%d' % self.scale_val()))) > 3:
                return True
            else:
                return False
        except:
            return False



    def numCorrSpots(self, s=None, l=None):
        if s == None: s = self.scale
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
        return self['timings']['levels'][self.scale]['t_align']

    @t_align.setter
    def t_align(self, dt):
        self['timings']['levels'][self.scale]['t_align'] = dt

    @property
    def t_generate(self):
        return self['timings']['levels'][self.scale]['t_generate']

    @t_generate.setter
    def t_generate(self, dt):
        self['timings']['levels'][self.scale]['t_generate'] = dt

    @property
    def t_convert_zarr(self):
        return self['timings']['levels'][self.scale]['t_convert_zarr']

    @t_convert_zarr.setter
    def t_convert_zarr(self, dt):
        self['timings']['levels'][self.scale]['t_convert_zarr'] = dt

    @property
    def t_thumbs_aligned(self):
        return self['timings']['levels'][self.scale]['t_thumbs_aligned']

    @t_thumbs_aligned.setter
    def t_thumbs_aligned(self, dt):
        self['timings']['levels'][self.scale]['t_thumbs_aligned'] = dt

    @property
    def t_thumbs_spot(self):
        return self['timings']['levels'][self.scale]['t_thumbs_spot']

    @t_thumbs_spot.setter
    def t_thumbs_spot(self, dt):
        self['timings']['levels'][self.scale]['t_thumbs_spot'] = dt

    @property
    def t_thumbs_matches(self):
        return self['timings']['levels'][self.scale]['t_thumbs_matches']

    @t_thumbs_matches.setter
    def t_thumbs_matches(self, dt):
        self['timings']['levels'][self.scale]['t_thumbs_matches'] = dt

    def set_thumb_scaling_factor_source(self, factor:int):
        self['timings']['thumb_scaling_factor_source'] = factor

    def set_thumb_scaling_factor_aligned(self, factor:int, s:str):
        self['timings']['levels'][s]['thumb_scaling_factor_aligned'] = factor

    def set_thumb_scaling_factor_corr_spot(self, factor:int, s:str):
        self['timings']['levels'][s]['thumb_scaling_factor_corr_spot'] = factor

    def normalize(self):
        return self._data['rendering']['normalize']

    def set_normalize(self, range):
        self._data['rendering']['normalize'] = range

    def notes(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['notes']


    def save_notes(self, text, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        self._data['stack'][l]['levels'][s]['notes'] = text

    def sl(self):
        return (self.scale, self.zpos)

    def to_json(self):
        return json.dumps(self._data)

    def to_dict(self):
        return self._data

    def dest(self) -> str:
        return self['location']


    def set_system_info(self):
        logger.info('')
        try:    self._data['system']['node'] = platform.node()
        except: self._data['system']['node'] = 'Unknown'

    def base_image_name(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # logger.info(f'Caller: {inspect.stack()[1].function}, s={s}, l={l}')
        return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['filename'])

    '''NEW METHODS USING NEW DATA SCHEMA 2023'''

    def filename(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['filename']

    def reference(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['reference']

    def filename_basename(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['filename'])

    def reference_basename(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['reference'])

    '''END OF NEW METHODS'''

    # def filenames(self):
    #     '''Returns filenames as absolute paths'''
    #     return natural_sort([os.path.abspath(l['filename'])
    #             for l in self._data['data']['scales'][self.scales[0]]['stack']])

    def basefilenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.basename(p) for p in self.series['paths']])


    def thumbnail_ref(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.join(self.dest(), 'thumbnails', os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings'][
            'reference']))


    def thumbnail_tra(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.join(self.dest(), 'thumbnails', os.path.basename(self._data['stack'][l]['levels'][s][
                                                                            'swim_settings']['filename']))

    def thumbnail_aligned(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        '''Returns absolute path of thumbnail for current layer '''
        return os.path.join(self.dest(), self.scale, 'thumbnails', self.filename_basename(s=s,l=l))


    def clobber(self):
        return self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings']['clobber_fixed_noise']

    def set_clobber(self, b, scales=None, stack=False):
        if scales == None: scales = self.finer_scales()
        for s in scales:
            if stack:
                for i in range(len(self)):
                    self['stack'][i]['levels'][s]['swim_settings']['clobber_fixed_noise'] = b
            else:
                self['stack'][self.zpos]['levels'][s]['swim_settings']['clobber_fixed_noise'] = b

    def clobber_px(self):
        return self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings']['clobber_size']

    def set_clobber_px(self, x, scales=None, stack=False):
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



    def get_signals_filenames(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        dir = os.path.join(self.dest(), 'signals', s)
        logger.info(f"dir: {dir}")
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        filename, extension = os.path.splitext(basename)
        pattern = '%s_%s_*%s' % (filename, self.current_method, extension)
        logger.info(f"pattern: {pattern}")
        paths = os.path.join(dir, pattern)
        names = natural_sort(glob(paths))
        # logger.info(f'Search Path: {paths}\nReturning: {names}')
        logger.info(f"Returning: {names}")
        return names

    def get_matches_filenames(self, s=None, l=None):
        if s == None: s = self.scale
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
        if s == None: s = self.scale
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
        return self.scales[-1]

    def layer_dict(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]

    def first_cafm_false(self):
        for l in range(len(self)):
            if not self.cafm_hash_comports(l=l):
                logger.info(f'returning {l}')
                return l
            # if not self._data['data']['scales'][self.scale_key]['stack'][l]['cafm_comports']:
            #     return l
        return None


    def isRefinement(self):
        return  self.scale != self.coarsest_scale_key()

    def get_source_img_paths(self):
        imgs = []
        for f in self.filenames():
            imgs.append(os.path.join(self.source_path(), os.path.basename(f)))
        return imgs

    def is_mendenhall(self):
        return self._data['data']['mendenhall']

    def get_iter(self, s=None, start=0, end=None):
        if s == None: s = self.scale
        return ScaleIterator(self['stack'][start:end])

    def references_list(self):
        return [x['levels'][self.scale]['swim_settings']['reference'] for x in self.get_iter()]

    def transforming_list(self):
        return [x['levels'][self.scale]['swim_settings']['filename'] for x in self.get_iter()]

    def get_index(self, filename):
        # logger.info(f'[{inspect.stack()[1].function}] filename = {filename}')
        # logger.info(f'filename = {filename}')
        return self.transforming_list().index(filename)

    def get_ref_index_offset(self, l=None):
        if l == None:
            l = self.zpos
        return l - self.get_ref_index(l=l)


    def datetime(self, s=None, l=None):
        if s == None: s = self.scale
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
        for s in self.scales:

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
        for s in self.scales[1:]:
            timings.append(('  ' + self.scale_pretty(s), '%s / %s' % (t7[s], t7m[s])))
        timings.append(('Convert Scales to Zarr', t1 + ' / ' + t1m + " (total)"))
        for s in self.scales:
            timings.append(('  ' + self.scale_pretty(s), '%s / %s' % (t8[s], t8m[s])))
        timings.append(('Compute Affines', ''))
        for s in self.scales:
            timings.append(('  ' + self.scale_pretty(s), '%s / %s' % (t3[s], t3m[s])))
        timings.append(('Generate Aligned TIFFs', ''))
        for s in self.scales:
            timings.append(('  ' + self.scale_pretty(s), '%s / %s' % (t4[s], t4m[s])))
        timings.append(('Convert Aligned TIFFs to Zarr', ''))
        for s in self.scales:
            timings.append(('  ' + self.scale_pretty(s), '%s / %s' % (t5[s], t5m[s])))
        timings.append(('Generate Aligned TIFF Thumbnails', ''))
        for s in self.scales:
            timings.append(('  ' + self.scale_pretty(s), '%s / %s' % (t6[s], t6m[s])))
        return timings


    def snr(self, s=None, l=None, method=None) -> float:
        if s == None: s = self.scale
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
        if s == None: s = self.scale
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
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            method = self.method(s=s, l=l)
            return self._data['stack'][l]['levels'][s]['alignment_history'][method]['method_results']['snr_report']
        except:
            logger.warning('No SNR Report for Layer %d' % l)
            return ''


    def snr_errorbar_size(self, s=None, l=None):
        if s == None: s = self.scale
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
        if s == None: s = self.scale
        return np.array([self.snr_errorbar_size(s=s, l=l) for l in range(0, len(self))])


    def check_snr_status(self, s=None) -> list:
        if s == None: s = self.scale
        unavailable = []
        for i,l in enumerate(self.stack(s=s)):
            if not 'snr' in l['method_results']:
                unavailable.append((i, self.name_base(s=s, l=i)))
        return unavailable


    def snr_max_all_scales(self) -> float:
        #Todo refactor, store local copy, this is a bottleneck
        max_snr = []
        try:
            for s in self.scales:
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
        if s == None: s = self.scale
        idx, val = zip(*nsmallest(n + 1, enumerate(self.snr_list()), key=itemgetter(1)))
        return zip(idx[1:], val[1:])


    def snr_average(self, scale=None) -> float:
        # logger.info('caller: %s...' % inspect.stack()[1].function)
        if scale == None: scale = self.scale
        # NOTE: skip the first layer which does not have an SNR value s may be equal to zero
        try:
            return statistics.fmean(self.snr_list(s=scale)[1:])
        except:
            logger.warning('No SNR data found - returning 0.0...')
            return 0.0


    def method(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['swim_settings']['method']
        except:
            print_exception(extra=f"Section #{l}")

    def method_pretty(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        convert = {'grid-default': 'Grid Default', 'grid-custom': 'Grid Custom',
                   'manual-strict': 'Manual Strict', 'manual-hint': 'Manual Hint'}
        return convert[self._data['stack'][l]['levels'][s]['swim_settings']['method']]


    def set_all_methods_automatic(self):
        '''Sets the alignment method of all sections and all scales to Auto-SWIM.'''
        for l in range(len(self)):
            self._data['stack'][l]['levels'][self.scale]['swim_settings']['method'] = 'grid-default'

        self.set_manual_swim_windows_to_default()

    def manpoints(self, s=None, l=None):
        '''Returns manual correspondence points in Neuroglancer format'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['match_points']

    def set_manpoints(self, role, matchpoints, l=None):
        '''Sets manual correspondence points for a single section at the current scale_key, and applies
         scaling factor then sets the same points for all scale_key levels above the current scale_key.'''
        if l == None: l = self.zpos
        logger.info(f"Writing manual points to project dictionary for section #{l}: {matchpoints}")
        # scale_vals  = [x for x in self.scale_vals() if x <= self.scale_val()]
        # scales      = [get_scale_key(x) for x in scale_vals]
        glob_coords = [None,None,None]
        fac = self.scale_val()
        for i,p in enumerate(matchpoints):
            if p:
                glob_coords[i] = (p[0] * fac, p[1] * fac)

        for s in self.finer_scales():
            # set manual points in Neuroglancer coordinate system
            fac = get_scale_val(s)
            coords = [None,None,None]
            for i,p in enumerate(glob_coords):
                if p:
                    coords[i] = (p[0] / fac, p[1] / fac)
            logger.info(f'Setting manual points for {s}: {coords}')
            self._data['stack'][l]['levels'][s]['swim_settings']['match_points'][role] = coords

            # set manual points in MIR coordinate system
            img_width = self.image_size(s=s)[0]
            mir_coords = [None,None,None]
            for i,p in enumerate(coords):
                if p:
                    mir_coords[i] = [img_width - p[1], p[0]]
            self._data['stack'][l]['levels'][s]['swim_settings']['match_points_mir'][role] = \
                mir_coords

    def manpoints_mir(self, role, s=None, l=None):
        '''Returns manual correspondence points in MIR format'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['match_points_mir'][role]

    def manpoints_pretty(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        ref = [x for x in self.manpoints()['ref'] if x is not None]
        base = [x for x in self.manpoints()['base'] if x is not None]
        return (['(%d, %d)' % (round(x1), round(y1)) for x1, y1 in ref],
                ['(%d, %d)' % (round(x1), round(y1)) for x1, y1 in base])


    def print_all_manpoints(self):
        logger.info('Match Points:')
        for i, sec in enumerate(self.stack()):
            r = sec['swim_settings']['match_points']['ref']
            b = sec['swim_settings']['match_points']['base']
            if r != []:
                logger.info(f'Index: {i}, Ref, Match Points: {str(r)}')
            if b != []:
                logger.info(f'Index: {i}, Base, Match Points: {str(b)}')


    def getmpFlat(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        mps = self._data['stack'][l]['levels'][s]['swim_settings']['match_points']
        # ref = [(0.5, x[0], x[1]) for x in mps['ref']]
        # base = [(0.5, x[0], x[1]) for x in mps['base']]

        d = {'ref': [None,None,None], 'base': [None,None,None]}
        for i in range(0,3):
            try:
                if mps['ref'][i]:
                    d['ref'][i] = (l, mps['ref'][i][0], mps['ref'][i][1])
            except:
                print_exception()
            try:
                if mps['base'][i]:
                    d['base'][i] = (l, mps['base'][i][0], mps['base'][i][1])
            except:
                print_exception()

        # ref = [(l, x[0], x[1]) for x in mps['ref']]
        # base = [(l, x[0], x[1]) for x in mps['base']]
        return d


    def afm(self, s=None, l=None) -> list:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            # return self._data['stack'][l]['levels'][s]['alignment']['method_results']['affine_matrix']
            method = self.method(s=s,l=l)
            return self._data['stack'][l]['levels'][s]['alignment_history'][method]['method_results'][
            'affine_matrix']
        except:
            print_exception()
            return [[[1, 0, 0], [0, 1, 0]]]

    #0802+
    def swim_settings_hashable(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # return [tuple(map(tuple, x)) for x in self.cafm_list(s=s,end=end)]
        # return hash(str(self.cafm_list(s=s,end=end)))
        try:
            return hash(str(self['stack'][l]['levels'][s]['swim_settings']))
        except:
            print_exception(extra=f's={s}, l={l}')


    def cafm(self, s=None, l=None) -> list:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            # return self._data['stack'][l]['levels'][s]['alignment']['method_results']['cumulative_afm'] #0802-
            method = self.method(s=s, l=l)
            return self._data['stack'][l]['levels'][s]['alignment_history'][method][
                'method_results']['cumulative_afm']
        except:
            # caller = inspect.stack()[1].function
            # print_exception(extra=f'Layer {l}, caller: {caller}')
            exi = sys.exc_info()
            logger.warning(f"[{l}] {exi[0]} {exi[1]}")
            return [[1, 0, 0], [0, 1, 0]]


    def afm_list(self, s=None, l=None) -> list:
        if s == None: s = self.scale
        lst = [self.afm(l=i) for i, l in enumerate(self.stack(s=s))]
        return lst


    def cafm_list(self, s=None, end=None) -> list:
        if s == None: s = self.scale
        if end == None:
            end = len(self)
        lst = []
        for i in range(0,end):
            if i < end:
                lst.append(self.cafm(s=s, l=i))
        return lst

    def set_stack_cafm(self, s=None):
        if s == None: s = self.scale
        SetStackCafm(self, scale=s, poly_order=self.default_poly_order)


    def cafm_hashable(self, s=None, end=None):
        if s == None: s = self.scale
        if end == None: end = self.zpos
        # return [tuple(map(tuple, x)) for x in self.cafm_list(s=s,end=end)]
        # return hash(str(self.cafm_list(s=s,end=end)))
        try:
            # return hash(str(self.cafm(s=s, l=end)))
            return hashstring(str(self.cafm(s=s, l=end)))
        except:
            caller = inspect.stack()[1].function
            print_exception(extra=f'end={end}, caller: {caller}')


    def cafm_registered_hash(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self['stack'][l]['levels'][s]['cafm_hash']


    def cafm_current_hash(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # return hash(str(self.cafm_list(s=s, end=l)))
        try:
            return self.cafm_hashable(s=s, end=l)
        except:
            print_exception(extra=f"scale={s}, section={l}")

    #Deprecated now registering cafm hash in SetStackCafm
    def register_cafm_hashes(self, indexes, s=None):
        logger.info('Registering cafm hashes...')
        if s == None: s = self.scale
        for i in indexes:
            self['stack'][i]['levels'][s]['cafm_hash'] = self.cafm_current_hash(l=i)


    def cafm_hash_comports(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self.cafm_registered_hash(s=s, l=l) == self.cafm_current_hash(s=s, l=l)


    def data_comports(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        caller = inspect.stack()[1].function
        # logger.critical(f"caller: {caller}, s={s}, l={l}")
        problems = []
        method = self.method(s=s, l=l)

        #Temporary
        if l == self.first_unskipped():
            return True, []

        if not self['stack'][l]['levels'][s]['alignment_history'][method]['complete']:
            problems.append((f"Alignment method '{method}' is incomplete", 1, 0))
            return False, problems

        cur = self['stack'][l]['levels'][s]['swim_settings']  # current
        mem = self['stack'][l]['levels'][s]['alignment_history'][method]['swim_settings'] # memory

        #Todo refactor, 'recent_method' key
        try:
            prev_method = self['stack'][l]['levels'][s]['method_results']['method']
            if prev_method != cur['method']:
                problems.append(('Method changed', prev_method, cur['method']))
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

        if method == 'grid-default':
            for key in self.defaults:
                if key in mem['defaults']:
                    if key in ('bounding_box', 'corrective-polynomial'):
                        continue

                    if self.defaults[key] != mem['defaults'][key]:
                        if type(mem['defaults'][key]) == dict and len(mem['defaults'][key]) == 1:
                            breadcrumb = 'defaults > %s > %s' % (key, mem['defaults'][key])
                        else:
                            breadcrumb = 'defaults > %s' % key
                        problems.append(('Inconsistent data (key: %s)' % breadcrumb, self.defaults[key],
                                         mem['defaults'][key]))

        else:
            if cur['whiten'] != mem['whiten']:
                problems.append(("Inconsistent data at signal whitening magnitude (key: whiten)",
                                 cur['whiten'], mem['whiten']))
            if cur['swim_iters'] != mem['swim_iters']:
                problems.append(("Inconsistent data at # SWIM iterations (key: swim_iters)",
                                 cur['swim_iters'], mem['swim_iters']))


        if method == 'grid-custom':
            keys = ['grid_custom_px_1x1', 'grid_custom_px_2x2', 'grid_custom_regions']
            for key in keys:
                if cur[key] != mem[key]:
                    problems.append((f"Inconsistent data (key: {key})", cur[key], mem[key]))

        if method in ('manual-hint', 'manual-strict'):
            if cur['match_points_mir'] != mem['match_points_mir']:
                problems.append((f"Inconsistent match points (key: match_points_mir)",
                                 cur['match_points_mir'], mem['match_points_mir']))

            if method == 'manual-hint':
                if cur['manual_swim_window_px'] != mem['manual_swim_window_px']:
                    problems.append((f"Inconsistent match region size (key: manual_swim_window_px)",
                                     cur['manual_swim_window_px'], mem['manual_swim_window_px']))
        # elif method == 'grid-custom':
        #     return cur['defaults'] == mem['defaults']
        return len(problems) == 0, problems
        # return tuple(comports?, [(reason/key, val1, val2)])


    def data_comports_indexes(self, s=None):
        if s == None: s = self.scale
        return np.array([self.data_comports(s=s, l=l)[0] for l in range(0, len(self))]).nonzero()[0].tolist()


    def data_dn_comport_indexes(self, s=None):
        if s == None: s = self.scale
        t0 = time.time()
        lst = [(not self.data_comports(s=s, l=l)[0]) and (not self.skipped(s=s, l=l)) for l in range(0, len(self))]
        t1 = time.time()
        indexes = np.array(lst).nonzero()[0].tolist()
        logger.info(f"dt = {time.time() - t0:.3g} ({t1 - t0:.3g}/{time.time() - t1:.3g})")
        return indexes


    def all_comports_indexes(self, s=None):
        if s == None: s = self.scale
        t0 = time.time()
        indexes = list(set(range(len(self))) - set(self.cafm_dn_comport_indexes(s=s)) - set(self.data_dn_comport_indexes(s=s)))
        logger.info(f"dt = {time.time() - t0:.3g}")
        return indexes


    def cafm_comports_indexes(self, s=None):
        if s == None: s = self.scale
        return np.array([self.cafm_hash_comports(s=s, l=l) for l in range(0, len(self))]).nonzero()[0].tolist()


    def cafm_dn_comport_indexes(self, s=None):
        if s == None: s = self.scale
        t0 = time.time()
        indexes = []
        for i in range(0, len(self)):
            if not self.cafm_hash_comports(s=s, l=i) or not self.data_comports(s=s, l=i)[0]:
                if not self.skipped(s=s, l=i):
                    indexes.append(i)

        logger.info(f"dt = {time.time() - t0:.3g}")
        return indexes


    def resolution(self, s=None):
        if s == None: s = self.scale
        return self['series']['settings']['levels'][str(self.scale_val())]['resolution']

    def set_resolution(self, s, res_x:int, res_y:int, res_z:int):
        self['series']['settings']['levels'][str(self.scale_val())]['resolution'] = (res_z, res_y, res_x)


    def get_user_zarr_settings(self):
        '''Returns user settings for cname, clevel, chunkshape as tuple (in that order).'''
        return (self.cname, self.clevel, self.chunkshape)

    def scale_pretty(self, s=None) -> str:
        if s == None: s = self.scale
        return 'Scale %d' % self.scale_val(s=s)

    def scale_val(self, s=None) -> int:
        if s == None: s = self.scale
        # caller = inspect.stack()[1].function
        # logger.critical(f"[{caller}]")
        # while s.startswith('scale_'):
        #     s = s[len('scale_'):]
        if s.startswith('scale_'):
            while s.startswith('scale_'):
                s = s[len('scale_'):]
            return int(s)
        elif s.startswith('s'):
            while s.startswith('s'):
                s = s[len('s'):]
            return int(s)
        else:
            return int(s)

    def scale_vals(self) -> list[int]:
        return [int(v) for v in sorted([get_scale_val(s) for s in self.scales])]

    def downscales(self) -> list[str]:
        '''Get downscales list (similar to scales() but with scale_1 removed).
        Faster than O(n*m) performance.
        Preserves order of scales.'''
        lst = natural_sort(self['series']['scale_keys'])
        try:
            lst.remove('s1')
        except:
            print_exception()
        return lst

    def skipped(self, s=None, l=None) -> bool:
        '''Called by get_axis_data'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            # return bool(self._data['stack'][l]['levels'][s]['skipped'])
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
        return bool(self._data['stack'][l]['levels'][s]['swim_settings']['include'])


    def set_skip(self, b: bool, s=None, l=None) -> None:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['stack'][l]['levels'][s]['skipped'] = b
        self._data['stack'][l]['levels'][s]['swim_settings']['include'] = not b


    def skips_list(self, s=None) -> list:
        '''Returns the list of excluded images for a s'''
        if s == None: s = self.scale
        indexes, names = [], []
        try:
            for i in range(0,len(self)):
                if not self['stack'][i]['levels'][s]['swim_settings']['include']:
                    indexes.append(i)
                    names.append(os.path.basename(self['stack'][i]['levels'][s]['swim_settings']['filename']))
            return list(zip(indexes, names))
        except:
            print_exception()
            logger.warning('Unable to To Return Skips List')
            return []

    def skips_indices(self, s=None) -> list:
        if s == None: s = self.scale
        try:
            return list(list(zip(*self.skips_list(s=s)))[0])
        except:
            return []

    def skips_by_name(self, s=None) -> list[str]:
        '''Returns the list of skipped images for a s'''
        if s == None: s = self.scale
        lst = []
        try:
            for i in range(len(self)):
                if not self.include(s=s,l=i):
                    f = os.path.basename(self['stack'][i]['levels'][s]['swim_settings']['filename'])
                    lst.append(f)
            return lst
        except:
            logger.warning('Unable to To Return Skips By Name List')
            return []


    def swim_iterations(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['iterations']


    def set_swim_iterations(self, val, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        self._data['stack'][l]['levels'][s]['swim_settings']['iterations'] = val
        self.signals.warning2.emit()
        
        
    def set_default_swim_iterations(self, val, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        self._data['defaults']['swim-iterations'] = val
        self.signals.warning2.emit()


    def swim_settings(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']


    def set_swim_iterations_glob(self, val:int, ):
        # for s in self.scales():
        for s in self.finer_scales():
            for i in range(len(self)):
                self['stack'][i]['levels'][s]['swim_settings']['iterations'] = val

    def whitening(self) -> float:
        '''Returns the Signal Whitening Factor for the Current Layer.'''
        return float(self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings']['signal-whitening'])


    def set_whitening(self, f: float) -> None:
        '''Sets the Whitening Factor for the Current Layer.'''
        self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings']['signal-whitening'] = f
        self.signals.warning2.emit()


    def swim_window(self) -> float:
        '''Returns the SWIM Window for the Current Layer.'''
        return float(self.stack()[self.zpos]['swim_settings']['win_scale_factor'])

    def swim_1x1_custom_px(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # return self.stack()[self.zpos]['swim_settings']]['grid-custom-px']
        return tuple(self._data['stack'][l]['levels'][s]['swim_settings']['grid_custom_px_1x1'])

    def set_swim_1x1_custom_px(self, pixels=None):
        '''Sets the SWIM Window for the Current Section across all scales.'''
        # if pixels == None:
        #     self.set_auto_swim_windows_to_default(current_only=True)
        if (pixels % 2) == 1:
            pixels -= 1
            if int(pixels/2) % 2 == 1:
                pixels -= 2
        img_w, img_h = self.image_size(s=self.scale)
        pixels = pixels
        pixels_y = (pixels / img_w) * img_h
        self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings'][
            'grid_custom_px_1x1']\
         = [
            pixels,
        pixels_y]
        if (self.swim_2x2_custom_px()[0] * 2) > pixels:
            self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings'][
            'grid_custom_px_2x2']\
                = \
                [int(pixels / 2  + 0.5), int(pixels_y / 2 + 0.5)]

        self.signals.warning2.emit()



    def propagate_swim_1x1_custom_px(self, indexes:list):
        '''Sets the SWIM Window for the Current Section across all scales.'''
        # img_w, img_h = self.image_size(s=self.scale_key)
        # logger.critical(f"caller: {caller_name()}")
        for l in indexes:
            pixels = self._data['stack'][l]['levels'][self.scale]['swim_settings'][
                'grid_custom_px_1x1']
            for s in self.finer_scales():
                sf = self.scale_val() / get_scale_val(s)
                self._data['stack'][l]['levels'][s]['swim_settings'][
                    'grid_custom_px_1x1'] = [int(pixels[0] * sf + 0.5), int(pixels[1] * sf + 0.5)]


    def swim_2x2_custom_px(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return tuple(self._data['stack'][l]['levels'][s]['swim_settings']['grid_custom_px_2x2'])

    def set_swim_2x2_custom_px(self, pixels=None):
        '''Returns the SWIM Window in pixels'''
        caller = inspect.stack()[1].function
        # if pixels == None:
        #     self.set_auto_swim_windows_to_default(current_only=True)
        if (pixels % 2) == 1:
            pixels -= 1

        img_w, img_h = self.image_size(s=self.scale)
        pixels_y = (pixels / img_w) * img_h

        if (2 * pixels) <= self.swim_1x1_custom_px()[0]:
            self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings'][
            'grid_custom_px_2x2'] = [pixels, pixels_y]
        else:
            force_pixels = [int(self.swim_1x1_custom_px()[0] / 2 + 0.5),int(self.swim_1x1_custom_px()[1] / 2 + 0.5)]
            if (force_pixels[0] % 2) == 1:
                force_pixels[0] -= 1
                force_pixels[1] -= 1
            self._data['stack'][self.zpos]['levels'][self.scale]['swim_settings'][
            'grid_custom_px_2x2']\
             = \
                force_pixels
        self.signals.warning2.emit()


    def propagate_swim_2x2_custom_px(self, indexes:list):
        '''Returns the SWIM Window in pixels'''
        # img_w, img_h = self.image_size(s=self.scale_key)
        for l in indexes:
            pixels = self._data['stack'][l]['levels'][self.scale]['swim_settings'][
            'grid_custom_px_2x2']
            for s in self.finer_scales(include_self=False):
                sf = self.scale_val() / get_scale_val(s)  # scale_key factor
                self._data['stack'][l]['levels'][s]['swim_settings']['grid_custom_px_2x2'] = [int(
                pixels[0]
                * sf
                                                                                                        + 0.5), int(pixels[1] * sf + 0.5)]


    #Todo 0612
    def set_auto_swim_windows_to_default(self, s_list=None, factor=None, current_only=False) -> None:

        if s_list == None:
            s_list = self.finer_scales()

        img_size = self.image_size(self.scales[0])  # largest scale_key size
        # man_ww_full = min(img_size[0], img_size[1]) * cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC
        if factor == None:
            factor = cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC
        man_ww_full = img_size[0] * factor, img_size[1] * factor
        # for s in self.scales():
        for s in s_list:
            man_ww_x = int(man_ww_full[0] / self.scale_val(s) + 0.5)
            man_ww_y = int(man_ww_full[1] / self.scale_val(s) + 0.5)

            # self._data['defaults'].setdefault(s, {})
            # self._data['defaults'][s]['swim-window-px'] = [man_ww_x, man_ww_y]
            if current_only:
                self['stack'][self.zpos]['levels'][s]['swim_settings']['grid_custom_px_1x1'] = [int(
                    man_ww_x),
                int(man_ww_y)]
                self['stack'][self.zpos]['levels'][s]['swim_settings']['grid_custom_px_2x2'] = [int(man_ww_x / 2 + 0.5),
                                                                                                int(man_ww_y / 2 + 0.5)]
            else:
                self._data['defaults'].setdefault(s, {})
                self._data['defaults'][s]['swim-window-px'] = [man_ww_x, man_ww_y]
                for i in range(len(self)):
                    # logger.critical(f"Setting grid_custom_px_1x1 for s={s}, index={i}...")
                    self['stack'][i]['levels'][s]['swim_settings']['grid_custom_px_1x1'] = [int(man_ww_x),
                                                                                            int(man_ww_y)]
                    self['stack'][i]['levels'][s]['swim_settings']['grid_custom_px_2x2'] = [int(man_ww_x / 2 +
                                                                                                     0.5),
                                                                                            int(man_ww_y/ 2 + 0.5)]
        self.signals.warning2.emit()

    def manual_swim_window_px(self, s=None, l=None) -> int:
        '''Returns the SWIM Window for the Current Layer.'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return int(self['stack'][l]['levels'][s]['swim_settings']['manual_swim_window_px'])

    def set_manual_swim_window_px(self, pixels=None) -> None:
        '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
        logger.info(f'Setting Local SWIM Window to [{pixels}] pixels...')

        if (pixels % 2) == 1:
            pixels -= 1

        self['stack'][self.zpos]['levels'][self.scale]['swim_settings'][
            'manual_swim_window_px'] = pixels
        self.signals.warning2.emit()


    def propagate_manual_swim_window_px(self, indexes) -> None:
        '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
        # logger.info('Propagating swim regions to finer scales...')
        for l in indexes:
            pixels = self['stack'][l]['levels'][self.scale]['swim_settings'][
                'manual_swim_window_px']
            for s in self.finer_scales():
                sf = self.scale_val() / get_scale_val(s)  # scale_key factor
                self['stack'][l]['levels'][s]['swim_settings']['manual_swim_window_px'] = \
                    int(pixels * sf + 0.5)

    def set_manual_swim_windows_to_default(self, s_list=None, current_only=False) -> None:
        logger.info('')
        if s_list == None:
            s_list = self.finer_scales()

        img_size = self.image_size(self.scales[0])  # largest scale_key size
        man_ww_full = min(img_size[0], img_size[1]) * cfg.DEFAULT_MANUAL_SWIM_WINDOW_PERC
        # for s in self.scales():
        for s in s_list:
            man_ww = man_ww_full / self.scale_val(s)
            # logger.info(f'Manual SWIM window size for {s} to {man_ww}')
            if current_only:
                self['stack'][self.zpos]['levels'][s]['swim_settings']['manual_swim_window_px'] = man_ww
            else:
                for i in range(len(self)):
                    self['stack'][i]['levels'][s]['swim_settings']['manual_swim_window_px'] = man_ww
        self.signals.warning2.emit()

    def image_size(self, s=None) -> tuple:
        if s == None: s = self.scale
        return tuple(self['series']['levels'][s]['size_xy'])


    def name_base(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return os.path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['filename'])
        except:
            return ''


    def has_bb(self, s=None) -> bool:
        '''Returns the Has Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.scale
        return bool(self['bounding_box'][s]['has'])


    def set_has_bb(self, b:bool, s=None):
        '''Returns the Has Bounding Rectangle On/Off State for the Current Scale.'''
        # logger.info(f'Setting HAS bb to {b}')
        if s == None: s = self.scale
        self['bounding_box'][s]['has'] = b


    def use_bb(self, s=None) -> bool:
        '''Returns the Use Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.scale
        return bool(self['bounding_box'][s]['use'])

    def set_use_bounding_rect(self, b: bool) -> None:
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        # self._data['defaults']['bounding-box'] = bool(b)
        self['bounding_box'][self.scale]['use'] = bool(b)

    def set_bounding_rect(self, bounding_rect: list, s=None) -> None:
        if s == None: s = self.scale
        self._data['bounding_box'][s]['size'] = bounding_rect

    def set_calculate_bounding_rect(self, s=None):
        if s == None: s = self.scale
        self.set_bounding_rect(ComputeBoundingRect(self))
        return self.bounding_rect()


    def coarsest_scale_key(self) -> str:
        '''Return the coarsest s key. '''
        #Confirmed
        return natural_sort(self['series']['scale_keys'])[-1]


    def finer_scales(self, s=None, include_self=True):
        if s == None: s = self.scale
        if include_self:
            return [get_scale_key(x) for x in self.scale_vals() if x <= self.scale_val(s=s)]
        else:
            return [get_scale_key(x) for x in self.scale_vals() if x < self.scale_val(s=s)]


    def first_unskipped(self, s=None):
        if s == None: s = self.scale
        for section in self.get_iter(s=s):
            if section['levels'][self.scale]['swim_settings']['include']:
                return section['levels'][self.scale]['swim_settings']['index']



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


    def link_reference_sections(self, s_list=None):
        logger.info('')
        if s_list == None:
            s_list = self.finer_scales()
        for s in s_list:
            skip_list = self.skips_indices(s=s)
            first_unskipped = self.first_unskipped(s=s)
            for layer_index in range(len(self)):
                base_layer = self['stack'][layer_index]
                j = layer_index - 1  # Find nearest previous non-skipped l
                while (j in skip_list) and (j >= 0):
                    j -= 1
                if (j not in skip_list) and (j >= 0):
                    ref = self['stack'][j]['levels'][s]['swim_settings']['filename']
                    # ref = os.path.join(self['series']['tiff_path'], s, ref)
                    # base_layer['images']['ref']['filename'] = ref
                    # base_layer['reference'] = ref
                    self['stack'][layer_index]['levels'][s]['swim_settings']['reference'] = ref
            self['stack'][first_unskipped]['levels'][s]['swim_settings']['reference'] = '' #0804



def get_scale_key(scale_val) -> str:
    '''Create a key like "scale_#" from either an integer or a string'''
    s = str(scale_val)
    while s.startswith('scale_'):
        s = s[len('scale_'):]
    # return 'scale_' + s
    return 's' + s


def get_scale_val(scale_of_any_type) -> int:
    '''Converts s key to integer (i.e. 'scale_1' as string -> 1 as int)
    TODO: move this to glanceem_utils'''
    scale = scale_of_any_type
    try:
        if type(scale) == type(1):
            return scale
        else:
            # while scale.startswith('scale_'):
            #     scale = scale[len('scale_'):]
            # return int(scale)
            while scale.startswith('s'):
                scale = scale[len('s'):]
            return int(scale)
    except:
        logger.warning('Unable to return s value')

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



if __name__ == '__main__':
    data = DataModel()
    print('Data Model Version: ' + str(data['version']))
    print(data)
