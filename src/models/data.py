#!/usr/bin/env python3

"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""
import copy
import inspect
import json
import logging
import os
import platform
import re
import statistics
import sys
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from glob import glob
from heapq import nsmallest
from operator import itemgetter
from pathlib import Path

import numpy as np
import zarr
from qtpy.QtCore import QObject, Signal

from src.utils.funcs_image import ComputeBoundingRect, SetStackCafm, alt_SetStackCafm
from src.models.cache import Cache
from src.utils.helpers import print_exception, path_to_str
from src.utils.writers import write
from src.core.files import DirectoryStructure
import src.config as cfg

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
    positionChanged = Signal(int)
    swimArgsChanged = Signal() #should prob be swimSettingsChanged
    outputSettingsChanged = Signal()
    swimSettingsChanged = Signal()


class Level:
    pass

class DataModel:

    """ Encapsulate datamodel dictionary and wrap with methods for convenience """
    def __init__(self, data=None, file_path=None, images_path=None, readonly=False, init=False, images_info=None):
        self._current_version = cfg.VERSION
        if data:
            self._data = data  # Load project data from file

        elif init:
            try:
                images_info
            except NameError:
                logger.warning(f"'series_info' argument is needed to initialize data model.")
                return
            try:
                file_path
            except NameError:
                logger.warning(f"'file_path' argument is needed to initialize data model.")
                return
            self._data = {}
            self.initializeStack(file_path, images_path, images_info)

        if not readonly:
            if images_path:
                self.images_path = images_path
            self.ht = None
            self.loadHashTable()
            self._upgradeDatamodel()
            self.signals = Signals()
            self.ds = DirectoryStructure(self)

        if readonly:
            clr = inspect.stack()[1].function
            logger.info(f"[{clr}] [{self['info']['file_path']}]")
            assert hasattr(self, '_data')

    def loadHashTable(self):
        logger.info('')
        self.ht = cfg.ht = Cache(self)


    def _upgradeDatamodel(self):
        logger.info('Upgrading data model...')
        if 'series_uuid' in self['info']:
            self['info']['images_uuid'] = self['info'].pop('series_uuid')
        if 'series_location' in self['info']:
            self['info']['images_path'] = self['info'].pop('series_location')


        self._data['modified'] = date_time()
        self['protected'].setdefault('force_reallocate_zarr_flag', False)
        self['state']['neuroglancer'].setdefault('transformed', True)
        # ident = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()
        for i in range(len(self)):
            for level in self.levels:
                d = self['stack'][i]['levels'][level]
                if 'saved_swim_settings' in d:
                    d.pop('saved_swim_settings')
                d.setdefault('results', {})
                # self['stack'][i]['levels'][level]['results'].setdefault('mir_afm', ident)
                # self['stack'][i]['levels'][level].setdefault('alt_cafm', np.array([[1., 0., 0.], [0., 1., 0.]]).tolist())

        for level in self.levels:
            if not 'chunkshape' in self['level_data'][level]:
                chunkshape = self.get_transforming_chunkshape(level)
                self['level_data'][level]['chunkshape'] = chunkshape
                self['protected']['force_reallocate_zarr_flag'] = True


    def __iter__(self):
        for section in cfg.pt.dm['stack']:
            yield section


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
        clr = inspect.stack()[1].function
        logger.info(f'Creating __deepcopy__ of DataModel [{clr}]...')
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    def __len__(self):
        try:
            return self['images']['count']
        except:
            logger.warning('No Images Found')

    @property
    def zattrs(self):
        path = os.path.join(self.data_dir_path, 'zarr', self.level)
        z = zarr.open(path)
        return z.attrs

    @property
    def zarr(self):
        path = os.path.join(self.data_dir_path, 'zarr', self.level)
        return zarr.open(path)


    def to_file(self):
        path = os.path.join(self.dest(), 'state_' + date_time() + '.swiftir')
        with open(path, 'w') as f:
            f.write(str(self.to_json()))

    @property
    def title(self):
        basename = os.path.basename(self['info']['file_path'])
        name, _ = os.path.splitext(basename)
        return name

    @property
    def count(self):
        return len(self)

    @property
    def basename(self) -> str:
        '''Get transforming image file_path.'''
        return self.SS['name']

    @property
    def refname(self) -> str:
        '''Get reference image file_path.'''
        return self.SS['reference_name']

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
    def images_path(self):
        '''Set alignment data images_path.'''
        return self['info']['images_path']

    @images_path.setter
    def images_path(self, p):
        '''Get alignment data images_path.'''
        self['info']['images_path'] = path_to_str(p)

    @property
    def data_file_path(self):
        '''Set alignment data images_path.'''
        return self['info']['file_path']

    @data_file_path.setter
    def data_file_path(self, p):
        '''Get alignment data images_path.'''
        self['info']['file_path'] = path_to_str(p)

    @property
    def data_dir_path(self):
        '''Set alignment data images_path.'''
        return Path(self['info']['file_path']).with_suffix('')

    def dest(self) -> str:
        return self['info']['file_path']

    @property
    def scales(self) -> list[str]:
        '''Get scale levels list.'''
        return natural_sort(self['images']['levels'])

    @property
    def levels(self) -> list[str]:
        '''Get scale levels list.'''
        return natural_sort(self['images']['levels'])

    @property
    def source_path(self):
        '''Get source file_path.'''
        return self['source_path']

    @source_path.setter
    def source_path(self, p):
        '''Set source file_path.'''
        self['source_path'] = path_to_str(p)

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
        return self['state']['z_position']

    @zpos.setter
    def zpos(self, pos):
        '''Set global Z-position. Signals UI to update.'''
        # clr = inspect.stack()[1].function
        # self['data']['Current Section (Index)'] = index
        pos = int(pos)
        if pos in range(0, len(self)):
            if pos != self.zpos:
                self['state']['z_position'] = pos
                self.signals.positionChanged.emit(pos)
        else:
            logger.warning(f'\nINDEX OUT OF RANGE: {pos} [clr: {inspect.stack()[1].function}]\n')

    @property
    def cname(self) -> str:
        '''Get compression type'''
        return self['images']['cname']

    @cname.setter
    def cname(self, x:str):
        '''Set compression type'''
        self['images']['cname'] = x

    @property
    def clevel(self) -> int:
        '''Get compression level'''
        return int(self['images']['clevel'])

    @clevel.setter
    def clevel(self, x:int):
        '''Set compression level'''
        self['images']['clevel'] = x


    def chunkshape(self, level=None) -> tuple:
        '''Get chunk shape for IMAGE STACK at RESOLUTION LEVEL 'level'.'''
        if level == None: level = self.level
        return tuple(self['images']['chunkshape'][level])


    def transforming_chunkshape(self, level):
        return self['level_data'][level]['chunkshape']

    def get_transforming_chunkshape(self, level):
        _, cy, cx = self.images['chunkshape'][level]
        return (cfg.BLOCKSIZE, cy, cx)

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
        return self['state']['level']

    @level.setter
    def level(self, s:str):
        self['state']['level'] = s


    @property
    def scale(self):
        return self['state']['level']

    @scale.setter
    def scale(self, s):
        self['state']['level'] = s

    # @property
    # def gif_speed(self):
    #     return self['state']['gif_speed']
    #
    # @gif_speed.setter
    # def gif_speed(self, s):
    #     self['state']['gif_speed'] = s

    @property
    def images(self):
        '''Returns the original images info for the alignment'''
        return self['images']


    @property
    def quadrants(self):
        '''property previously called grid_custom_regions'''
        return self.SS['method_opts']['quadrants']

    @quadrants.setter
    def quadrants(self, lst):
        '''property previously called grid_custom_regions'''
        # for level in self.levels():
        self.SS['method_opts']['quadrants'] = lst
        self.signals.swimArgsChanged.emit()

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
        try:
            assert self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method'] == 'grid'
        except:
            print_exception(extra=f"[{s}, {l}] method: {self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method']}")
            return None
        return self['stack'][l]['levels'][s]['swim_settings']['method_opts']['quadrants']


    @property
    def poly_order(self):
        return self['level_data'][self.level]['output_settings']['polynomial_bias']

    @poly_order.setter
    def poly_order(self, use):
        self['level_data'][self.level]['output_settings']['polynomial_bias'] = use

    # def whitening(self) -> float:
    #     '''Returns the Signal Whitening Factor for the Current Layer.'''
    #     return float(self.SS['whitening'])

    @property
    def whitening(self):
        return float(self.SS['whitening'])

    @whitening.setter
    def whitening(self, x):
        self.SS['whitening'] = float(x)
        self.signals.swimArgsChanged.emit()

    #Todo this isn't right!
    @property
    def defaults(self):
        return self['level_data'][self.level]['defaults']

    @defaults.setter
    def defaults(self, d, level=None):
        if level == None:
            level = self.level
        self['level_data'][level]['defaults'] = d

    # layer['swim_settings']].setdefault('karg', False)

    @property
    def gif(self):
        name, _ = os.path.splitext(self.basename)
        return os.path.join(self.data_dir_path, 'gif', self.level, name + '.gif')

    def writeDir(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        # cafm_hash = str(self.cafmHash(s=s, l=l))
        # file_path = os.file_path.join(self.file_path, 'data', str(l), s, ss_hash, cafm_hash)
        path = os.path.join(self.data_dir_path, 'data', str(l), s, ss_hash)
        return path

    def writeDirCafm(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        cafm_hash = str(self.cafmHash(s=s, l=l))
        path = os.path.join(self.data_dir_path, 'data', str(l), s, ss_hash, cafm_hash)
        return path

    @property
    def SS(self):
        '''Return SWIM preferences as copy of dict representing the current section'''
        return self._data['stack'][self.zpos]['levels'][self.level]['swim_settings']


    def ssDir(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        path = os.path.join(self.data_dir_path, 'data', str(l), s, ss_hash)
        return path

    def isAligned(self, s=None, l=None) -> bool:
        if s == None: s = self.level
        if l == None: l = self.zpos
        path = os.path.join(self.ssDir(), 'results.json')
        return os.path.exists(path)

    def path(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return os.path.join(self.images_path, 'tiff', s, self.name(s=s, l=l))

    def path_ref(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        if l == self.first_included():
            return self.path(s=s, l=l)
        else:
            try:
                return os.path.join(self.images_path, 'tiff', s, self.name_ref(s=s, l=l))
            except:
                print_exception(f'Section #{l}, Resolution Level {s}')

    def path_zarr_transformed(self, s=None):
        if s == None: s = self.level
        return os.path.join(self.data_dir_path, 'zarr', s)

    def get_zarr_transforming(self, s=None):
        if s == None: s = self.level
        path = self.path_zarr_transformed(s=s)
        meta = os.path.join(path, '.zarray')
        if os.path.exists(meta):
            try:
                return zarr.open(path)
            except OSError:
                print_exception(extra="Unable to open the transformed Zarr")

    def path_zarr_raw(self, s=None):
        if s == None: s = self.level
        return os.path.join(self.images_path, 'zarr', s)


    def path_aligned(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        # name = self.name(s=s, l=l)
        fn, ext = os.path.splitext(self.name(s=s, l=l))
        # file_path = os.file_path.join(self.writeDir(s=s, l=l), name)
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
        path = os.path.join(self['info']['images_path'], 'thumbs', self.name(s=s, l=l))
        return path

    def path_thumb_src_ref(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        i = self.get_ref_index(l=l)
        path = os.path.join(self['info']['images_path'], 'thumbs', self.name(s=s, l=i))
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
        path = os.path.join(self.data_dir_path, 'data', str(l), s, ss_hash, 'signals')
        return path

    def dir_matches(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        path = os.path.join(self.data_dir_path, 'data', str(l), s, ss_hash, 'matches')
        return path

    def dir_tmp(self, s=None, l=None) -> str:
        if s == None: s = self.level
        if l == None: l = self.zpos
        ss_hash = str(self.ssHash(s=s, l=l))
        path = os.path.join(self.data_dir_path, 'data', str(l), s, ss_hash, 'tmp')
        return path

    def section(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]


    def get_ref_index(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        # clr = inspect.stack()[1].function
        # logger.critical(f'clr: {clr}, z={z}')
        # if self.skipped(level=self.level, z=z):
        # if not self.include(s=self.level, l=l):
        #     return self.get_index(self._data['stack'][l]['levels'][self.level]['swim_settings']['file_path']) #Todo refactor this but not sure how
        # reference = self._data['stack'][l]['levels'][self.level]['swim_settings']['reference']
        # if reference == '':
        #     logger.warning('Reference is an empty string')
        #     return self.get_index(self._data['stack'][l]['levels'][self.level]['swim_settings']['file_path'])
        # return self.get_index(reference)
        try:
            return self.swim_settings(s=s, l=l)['reference_index']
        except:
            print_exception()
            return None

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
        # logger.info(f'clr: {inspect.stack()[1].function}, level={level}, z={z}')
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
        # return os.file_path.basename(self._data['stack'][l]['levels'][s]['swim_settings']['reference'])


    def basefilenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.basename(p) for p in self.images['paths']])


    def clobber(self):
        return self.SS['clobber']

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
                    self.signals.swimArgsChanged.emit()

    def clobber_px(self):
        return self.SS['clobber_size']

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
                    self.signals.swimArgsChanged.emit()

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
        # paths = natural_sort(glob(os.file_path.join(dir_signals, pattern)))
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
    #         imgs.append(os.file_path.join(self.source_path(), os.file_path.basename(f)))
    #     return imgs

    def is_mendenhall(self):
        return self['data']['mendenhall']

    def get_iter(self, s=None, start=0, end=None):
        if s == None: s = self.level
        return ScaleIterator(self['stack'][start:end])

    def references_list(self):
        return [x['levels'][self.level]['swim_settings']['reference'] for x in self.get_iter()]

    def transforming_list(self):
        return [x['levels'][self.level]['swim_settings']['file_path'] for x in self.get_iter()]

    def transforming_bn_list(self):
        return [os.path.basename(x['levels'][self.level]['swim_settings']['file_path']) for x in self.get_iter()]

    def get_index(self, filename):
        # logger.info(f'[{inspect.stack()[1].function}] file_path = {file_path}')
        # logger.info(f'file_path = {file_path}')
        bn = os.path.basename(filename)
        return self.transforming_bn_list().index(bn)

    def get_ref_index_offset(self, l=None):
        if l == self.first_included():  #1007+
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
        except Exception as e:
            # tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # exi = sys.exc_info()
            # txt = f" [{tstamp}] Error Type/Value : {exi[0]} / {exi[1]}"
            logger.warning(f"[{l}] Failed to get SNR data from results. Reason: {e.__class__.__name__}")
            return 0.


    def snr_list(self, s=None) -> list[float]:
        try:
            return [self.snr(s=s, l=i) for i in range(len(self))]
        except Exception as e:
            logger.warning(f"Failed to create SNR list. Reason: {e.__class__.__name__}")
            return [0] * len(self)

    def indexes_to_snr_list(self, indexes, s=None) -> list[float]:
        return [self.snr(s=s, l=i) for i in indexes]


    def delta_snr_list(self, after, before):
        return [a_i - b_i for a_i, b_i in zip(after, before)]


    def snr_components(self, s=None, l=None, method=None) -> list[float]:
        clr = inspect.stack()[1].function
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
            logger.warning(f'No SNR components for section {l}, method {method} [clr: {clr}]...\n')
            return []



    def snr_errorbar_size(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['results']['snr_std_deviation']
        except Exception as e:
            logger.warning(f"[{l}] Unknown error bar size. Reason: {e.__class__.__name__}")
            return 0.



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
            clr = inspect.stack()[1].function
            logger.warning('Unable to append maximum SNR, none found (%s) - Returning Empty List' % clr)
            return 0.0


    def snr_lowest(self, n, s=None) -> zip:
        '''Returns the lowest n snr indices '''
        if s == None: s = self.level
        idx, val = zip(*nsmallest(n + 1, enumerate(self.snr_list()), key=itemgetter(1)))
        return zip(idx[1:], val[1:])


    def snr_mean(self, scale=None) -> float:
        # logger.info('clr: %level...' % inspect.stack()[1].function)
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
            if 'method_opts' in self.SS:
                return self.SS['method_opts']['method']
            else:
                return None
        except:
            print_exception()
            return

    @current_method.setter
    def current_method(self, str):
        self.SS['method_opts']['method'] = str
        self.signals.swimArgsChanged.emit()


    def method(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            if 'method_opts' in self.SS:
                return self.SS['method_opts']['method']
            else:
                return None
        except:
            print_exception(extra=f"Section #{l}")

    def method_pretty(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        convert = {'grid': 'Grid Align', 'manual': 'Manual Align'}
        return convert[self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['method']]

    # def manpoints(self, s=None, l=None):
    #     '''Returns manual correspondence points in Neuroglancer format'''
    #     if s == None: s = self.level
    #     if l == None: l = self.zpos
    #     return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['ng_coords']
    #
    # def set_manpoints(self, role, matchpoints, s=None, l=None):
    #     '''Sets manual correspondence points for a single section at the current level, and applies
    #      scaling factor then sets the same points for all scale levels above the current level.'''
    #     if s == None: s = self.scale
    #     if l == None: l = self.zpos
    #
    #     BEFORE = self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']
    #     logger.critical(f"Writing points to data: {matchpoints}")
    #     # ex. [(397.7689208984375, 546.7693481445312), (nan, nan), (nan, nan)]
    #     # lvls  = [x for x in self.lvls() if x <= self.lvl()]
    #     # scales      = [get_scale_key(x) for x in lvls]
    #     glob_coords = [None,None,None]
    #     fac = self.lvl()
    #     for i,p in enumerate(matchpoints):
    #         # (774.73145, 667.3542)
    #         # (None, None)
    #         if p:
    #             try:
    #                 glob_coords[i] = (p[0] * fac, p[1] * fac)
    #             except:
    #                 print_exception(extra=f"p: {p}")
    #
    #     # set manual points in Neuroglancer coordinate system
    #     # logger.critical(f"glob coords: {glob_coords}")
    #     fac = self.lvl(s)
    #     coords = [None,None,None]
    #     for i,p in enumerate(glob_coords):
    #         if p and p[0]:
    #                 coords[i] = (p[0] / fac, p[1] / fac)
    #     logger.info(f'Setting manual points for {s}: {coords}')
    #     # self._data['stack'][z]['levels'][level]['swim_settings']['match_points'][role] = coords
    #     self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['ng_coords'][role] = coords
    #
    #     # set manual points in MIR coordinate system
    #     img_width = self.image_size(s=s)[0]
    #     mir_coords = [None,None,None]
    #     for i,p in enumerate(coords):
    #         if p:
    #             mir_coords[i] = [img_width - p[1], p[0]]
    #     self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['mir_coords'][role] = mir_coords
    #
    #     self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points'].setdefault('coords', {'tra':[None]*3, 'ref':[None]*3})
    #
    #     AFTER = self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']
    #
    #     logger.critical(f"\n------------------"
    #                     f"\nBefore : {BEFORE}"
    #                     f"\n After : {AFTER}"
    #                     f"\n------------------")

    def manpoints_mir(self, role, s=None, l=None):
        '''Returns manual correspondence points in MIR format'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['points']['mir_coords'][role]
        except:
            print_exception(extra=f"role: {role}, s={s}, l={l}")


    def afm(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self['stack'][l]['levels'][s]['mir_afm']
        except Exception as e:
            logger.warning(f"[{l}] afm key not found in result data. Reason: {e.__class__.__name__}")
            return [[[1, 0, 0], [0, 1, 0]]]

    def mir_afm(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self['stack'][l]['levels'][s]['mir_afm']
        except Exception as e:
            logger.warning(f"[{l}] mir_afm key not found in result data. Reason: {e.__class__.__name__}")
            return [[[1, 0, 0], [0, 1, 0]]]

    def mir_aim(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self['stack'][l]['levels'][s]['mir_aim']
        except Exception as e:
            logger.warning(f"[{l}] mir_aim key not found in result data. Reason: {e.__class__.__name__}")
            return [[[1, 0, 0], [0, 1, 0]]]

    def cafm(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['cafm']
        except Exception as e:
            logger.warning(f"[{l}] cafm key not found in result data. Reason: {e.__class__.__name__}")
            return [[[1, 0, 0], [0, 1, 0]]]

    def alt_cafm(self, s=None, l=None) -> list:
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
            return self._data['stack'][l]['levels'][s]['alt_cafm']
        except Exception as e:
            logger.warning(f"[{l}] alt_cafm key not found in result data. Reason: {e.__class__.__name__}")
            return [[[1, 0, 0], [0, 1, 0]]]


    def cafmHash(self, s=None, l=None):
        return abs(hash(str(self.cafm(s=s, l=l))))



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
        alt_SetStackCafm(self, scale=s, poly_order=self.poly_order)


    # #Deprecated now registering cafm hash in SetStackCafm
    # def register_cafm_hashes(self, indexes, s=None):
    #     logger.info('Registering cafm data...')
    #     if s == None: s = self.level
    #     for i in indexes:
    #         self['stack'][i]['levels'][s]['cafm_hash'] = self.cafmHash(s=s, l=i)

    def isDefaults(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        _cur = copy.deepcopy(self['stack'][l]['levels'][s]['swim_settings'])
        _def = copy.deepcopy(self['level_data'][s]['defaults'])
        to_remove = ('index', 'name', 'level', 'is_refinement', 'img_size', 'init_afm', 'reference_index', 'reference_name')
        for k in to_remove:
            _cur.pop(k, None)
        return _cur == _def


    def needsAlignIndexes(self, s=None):
        if s == None: s = self.level
        #Todo make this not use global
        do = []
        for i in range(len(self)):
            if not self.ht.haskey(self.swim_settings(s=s, l=i)):
                do.append(i)
        return do


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
            #     # if not os.file_path.exists(self.path_aligned(s=s, l=i)):
            #     if not os.file_path.exists(self.path_aligned_cafm(s=s, l=i)):
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
    #             # if not os.file_path.exists(self.path_aligned(s=s, l=i)):
    #             if not os.file_path.exists(self.path_aligned_cafm(s=s, l=i)):
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

    def resolution(self, s=None):
        if s == None: s = self.level
        return self['images']['resolution'][s]

    def set_resolution(self, s, res_x:int, res_y:int, res_z:int):
        if s == None: s = self.level
        self['images']['resolution'][s] = (res_z, res_y, res_x)

    def get_images_zarr_settings(self):
        '''Returns user preferences for cname, clevel, chunkshape as tuple (in that order).'''
        return (self.cname, self.clevel, self.chunkshape())

    def get_transforming_zarr_settings(self, level):
        '''Returns user preferences for cname, clevel, chunkshape as tuple (in that order).'''
        return (self.cname, self.clevel, self.transforming_chunkshape(level))

    def downscales(self) -> list[str]:
        '''Get downscales list (similar to scales() but with scale_1 removed).
        Faster than O(n*m) performance.
        Preserves order of scales.'''
        downscales = natural_sort(self['images']['levels'])
        downscales.remove('s1')
        return downscales

    def skipped(self, s=None, l=None) -> bool:
        '''Called by get_axis_data'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        try:
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


    def set_include(self, b: bool, s=None, l=None) -> None:
        if s == None: s = self.level
        if l == None: l = self.zpos
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self.SS['include'] = b
        self.signals.swimArgsChanged.emit()

    def skips_list(self, level=None) -> list:
        '''Returns the list of excluded images for a level'''
        if level == None: level = self.level
        indexes, names = [], []
        try:
            for i in range(0,len(self)):
                if not self['stack'][i]['levels'][level]['swim_settings']['include']:
                    indexes.append(i)
                    # names.append(os.file_path.basename(self['stack'][i]['levels'][level]['swim_settings']['file_path']))
                    names.append(os.path.basename(self['stack'][i]['levels'][level]['swim_settings']['name']))
            return list(zip(indexes, names))
        except:
            print_exception()
            logger.warning('Unable to To Return Skips List')
            return []

    def exclude_indices(self, s=None) -> list:
        if s == None: s = self.level
        indexes = []
        for i in range(len(self)):
            if not self.include(s=s, l=i):
                indexes.append(i)
        return indexes


    def swim_iterations(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        return self._data['stack'][l]['levels'][s]['swim_settings']['iterations']


    def set_swim_iterations(self, val, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        self._data['stack'][l]['levels'][s]['swim_settings']['iterations'] = val
        self.signals.swimArgsChanged.emit()

    def swim_settings(self, s=None, l=None):
        '''Returns SWIM preferences as a hashable dictionary'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return HashableDict(self._data['stack'][l]['levels'][s]['swim_settings'])
        # return self._data['stack'][l]['levels'][s]['swim_settings']


    def ssHash(self, s=None, l=None):
        '''Returns SWIM preferences as a hashable dictionary'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        # return abs(hash(HashableDict(self.swim_settings(s=s, l=l))))
        return abs(hash(self.swim_settings(s=s, l=l)))



    def unknownAnswerIndexes(self, s=None):
        if s == None: s = self.level
        indexes = []
        for i in range(len(self)):
            try:
                assert np.array(self['stack'][i]['levels'][s]['mir_afm']).shape == (2, 3)
            except:
                indexes.append(i)
        return indexes



    def zarrCafmHashComports(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        fu = self.first_included()
        if l == fu:
            return True

        try:
            zarr_cafm_hash = self.zattrs[str(l)][1]
        except KeyError:
            return False

        cur_cafm_hash = str(self.cafmHash(s=s, l=l))
        # if cur_cafm_hash == zarr_cafm_hash:
        #     logger.info(f"Cache hit {cur_cafm_hash}! Zarr is correct at index {l}.")
        return zarr_cafm_hash == cur_cafm_hash

    def aa1x1(self, val):
        val = ensure_even(val)
        img_w, img_h = self.image_size(s=self.level)
        val_y = ensure_even(int((val / img_w) * img_h))
        self['level_data'][self.level]['defaults']['method_opts']['size_1x1'] = [val, val_y]
        cfg.mw.tell(f"Setting default 1x1 SWIM window: x,y = {val},{val_y}")
        for i in range(len(self)):
            if self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['method'] == 'grid':
                self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['size_1x1'] = [val, val_y]
        self.signals.swimArgsChanged.emit()

    def aa2x2(self, val):
        val = ensure_even(val)
        img_w, img_h = self.image_size(s=self.level)
        val_y = ensure_even(int((val / img_w) * img_h))
        self['level_data'][self.level]['defaults']['method_opts']['size_2x2'] = [val, val_y]
        cfg.mw.tell(f"Setting default 2x2 SWIM window: x,y = {val},{val_y}")
        for i in range(len(self)):
            if self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['method'] == 'grid':
                self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['size_2x2'] = [val, val_y]
        self.signals.swimArgsChanged.emit()

    def aaQuadrants(self, lst):
        cfg.mw.tell(f"Setting default SWIM grid quadrants: {lst}")
        self['level_data'][self.level]['defaults']['method_opts']['quadrants'] = lst
        for i in range(len(self)):
            if self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['method'] == 'grid':
                self['stack'][i]['levels'][self.level]['swim_settings']['method_opts']['quadrants'] = lst
        self.signals.swimArgsChanged.emit()

    def aaIters(self, val):
        cfg.mw.tell(f"Setting default SWIM iterations: {val}")
        self['level_data'][self.level]['defaults']['iterations'] = val
        for i in range(len(self)):
            self['stack'][i]['levels'][self.level]['swim_settings']['iterations'] = val
        self.signals.swimArgsChanged.emit()

    def aaWhitening(self, val):
        cfg.mw.tell(f"Setting default SWIM whitening factor: {val}")
        self['level_data'][self.level]['defaults']['whitening'] = val
        for i in range(len(self)):
            self['stack'][i]['levels'][self.level]['swim_settings']['whitening'] = val
        self.signals.swimArgsChanged.emit()

    def aaClobber(self, tup):
        if tup[0]:
            cfg.mw.tell(f"Setting default fixed-pattern noise clobber: {tup[0]}, {tup[1]}")
        else:
            cfg.mw.tell(f"Setting default fixed-pattern noise clobber: {tup[0]}")
        self['level_data'][self.level]['defaults']['clobber'] = tup[0]
        self['level_data'][self.level]['defaults']['clobber_size'] = tup[1]
        for i in range(len(self)):
            self['stack'][i]['levels'][self.level]['swim_settings']['clobber'] = tup[0]
            self['stack'][i]['levels'][self.level]['swim_settings']['clobber_size'] = tup[1]
        self.signals.swimArgsChanged.emit()


    def size1x1(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        # return self.stack()[self.zpos]['swim_settings']]['grid-custom-px']
        assert self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method'] == 'grid'
        return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['size_1x1']

    def set_size1x1(self, pixels=None, silent=False):
        '''Sets the SWIM Window for the Current Section across all scales.'''
        pixels = ensure_even(pixels)
        img_w, img_h = self.image_size(s=self.level)
        pixels = pixels
        pixels_y = (pixels / img_w) * img_h
        self.SS['method_opts']['size_1x1'] = [pixels,pixels_y]
        if (self.size2x2()[0] * 2) > pixels:
            self.SS['method_opts']['size_2x2'] = [int(pixels / 2  + 0.5), int(pixels_y / 2 + 0.5)]
        if not silent:
            self.signals.swimArgsChanged.emit()

    def size2x2(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        assert self['stack'][l]['levels'][s]['swim_settings']['method_opts']['method'] == 'grid'
        return self._data['stack'][l]['levels'][s]['swim_settings']['method_opts']['size_2x2']


    def set_size2x2(self, pixels=None, silent=False):
        '''Returns the SWIM Window in pixels'''
        # clr = inspect.stack()[1].function
        pixels = ensure_even(pixels)

        img_w, img_h = self.image_size(s=self.level)
        pixels_y = (pixels / img_w) * img_h

        if (2 * pixels) <= self.size1x1()[0]:
            self.SS['method_opts']['size_2x2'] = [pixels, pixels_y]
        else:
            force_pixels = [int(self.size1x1()[0] / 2 + 0.5), int(self.size1x1()[1] / 2 + 0.5)]
            if (force_pixels[0] % 2) == 1:
                force_pixels[0] -= 1
                force_pixels[1] -= 1
            self.SS['method_opts']['size_2x2'] = force_pixels
        if not silent:
            self.signals.swimArgsChanged.emit()


    def manual_swim_window_px(self, s=None, l=None) -> int:
        '''Returns the SWIM Window for the Current Layer.'''
        if s == None: s = self.level
        if l == None: l = self.zpos
        return ensure_even(self['stack'][l]['levels'][s]['swim_settings']['method_opts']['size'] * self.image_size()[0])

    # def set_manual_swim_window_px(self, pixels=None, silent=False) -> None:
    #     '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
    #     logger.info(f'Setting Local SWIM Window to [{pixels}] pixels...')
    #
    #     pixels = ensure_even(pixels)
    #
    #     dec = float(pixels / self.image_size()[0])
    #
    #     self.SS['method_opts']['size'] = dec
    #     if not silent:
    #         self.signals.swimArgsChanged.emit()

    def set_manual_swim_window_dec(self, dec:float, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        dec = float(dec)
        assert dec < 1
        assert dec > 0
        self.SS['method_opts']['size'] = dec
        self.signals.swimArgsChanged.emit()


    def image_size(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['images']['size_xy'][s])

    def size_xy(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['images']['size_xy'][s])

    def size_zyx(self, s=None) -> tuple:
        if s == None: s = self.level
        return tuple(self['images']['size_zyx'][s])


    def has_bb(self, s=None) -> bool:
        '''Returns the Has Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.level
        return bool(self['level_data'][s]['output_settings']['bounding_box']['has'])

    def use_bb(self, s=None) -> bool:
        '''Returns the Use Bounding Rectangle On/Off.'''
        if s == None: s = self.level
        return bool(self['level_data'][s]['output_settings']['bounding_box']['use'])

    def set_use_bounding_rect(self, b: bool, s=None) -> None:
        '''Sets the Bounding Rectangle On/Off.'''
        logger.info(f'Setting use bounding box to: {b}')
        if s == None: s = self.level
        self['level_data'][s]['output_settings']['bounding_box']['use'] = bool(b)

    def output_settings(self, s=None):
        if s == None: s = self.level
        return self['level_data'][s]['output_settings']

    def bounding_rect_dims(self, s=None):
        if s == None: s = self.level
        return self['level_data'][s]['output_settings']['bounding_box']['dims']


    def set_calculate_bounding_rect(self, s=None):
        if s == None: s = self.level
        dims = ComputeBoundingRect(self)
        self['level_data'][s]['output_settings']['bounding_box']['dims'] = dims
        return dims


    def coarsest_scale_key(self) -> str:
        '''Return the coarsest level key. '''
        #Confirmed
        return natural_sort(self['images']['levels'])[-1]


    def finer_scales(self, s=None, include_self=True):
        if s == None: s = self.level
        if include_self:
            return [self.level_key(x) for x in self.lvls() if x <= self.lvl(s=s)]
        else:
            return [self.level_key(x) for x in self.lvls() if x < self.lvl(s=s)]


    def first_included(self, s=None):
        # logger.info(f"{clr_name()}")
        if s == None: s = self.level
        for section in self.get_iter(s=s):
            # print(section['levels'][s]['swim_settings'])
            if section['levels'][s]['swim_settings']['include']:
                return section['levels'][s]['swim_settings']['index']


    def linkReference(self, s=None):
        if s == None:
            s = self.level
        logger.info(f'[{s}]')
        skip_list = self.exclude_indices(s=s)
        for i in range(len(self)):
            j = i - 1  # Find nearest previous non-skipped z
            while (j in skip_list) and (j >= 0):
                j -= 1
            if (j not in skip_list) and (j >= 0):
                ref = self.path(s=s, l=j)
                # self['stack'][layer_index]['levels'][level]['swim_settings']['reference'] = ref
                self['stack'][i]['levels'][s]['swim_settings']['reference_index'] = j
                self['stack'][i]['levels'][s]['swim_settings']['reference_name'] = os.path.basename(ref)
        # self['stack'][self.first_included(s=level)]['levels'][level]['swim_settings']['reference'] = ''  # 0804
        self['stack'][self.first_included(s=s)]['levels'][s]['swim_settings']['reference_index'] = None
        self['stack'][self.first_included(s=s)]['levels'][s]['swim_settings']['reference_name'] = None



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
        self['level_data'][self.level]['defaults'].update(copy.deepcopy(new_settings))
        for l in range(0, len(self)):
            #Check if default preferences are in use for each layer, if so, update with new preferences
            if self.isDefaults(l=l):
                self['stack'][l]['levels'][self.level]['swim_settings'].update(copy.deepcopy(new_settings))
        self.signals.swimArgsChanged.emit()

    def applyDefaults(self, s=None, l=None):
        if s == None: s = self.level
        if l == None: l = self.zpos
        def_settings = copy.deepcopy(self['level_data'][self.level]['defaults'])
        logger.info(f"Applying default preferences...")
        self['stack'][l]['levels'][s]['swim_settings'].update(def_settings)
        self.signals.swimArgsChanged.emit()

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

        fullsize = np.array(self['images']['size_xy'][self.levels[0]], dtype=int)
        s1_size_1x1 = fullsize * cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC

        d = {v: {} for v in self.levels}
        for level, v in d.items():

            factor = int(level[1:])
            _1x1 = np.rint(s1_size_1x1 / factor).astype(int).tolist()
            _2x2 = np.rint(s1_size_1x1 / factor / 2).astype(int).tolist()
            # Temporary ^. Take first value only. This should perhaps be rectangular, two-value.
            _1x1 = ensure_even(_1x1, extra='1x1 size')
            _2x2 = ensure_even(_2x2, extra='2x2 size')
            # man_ww_full = min(fullsize[0], fullsize[1]) * cfg.DEFAULT_MANUAL_SWIM_WINDOW_PERC
            # _man_ww = ensure_even(man_ww_full / int(level[1:]))

            v.update(
                manual={
                    'method': 'manual',
                    'mode': 'hint',
                    # 'size': _man_ww,
                    'size': cfg.DEFAULT_MANUAL_SWIM_WINDOW_PERC,
                    'points':{
                        'coords': {'tra': [None] * 3, 'ref': [None] * 3},

                        # 'ng_coords': {'tra': [], 'ref': []},
                        # 'mir_coords': {'tra': [], 'ref': []},
                        'ng_coords': {'tra': ((None, None), (None, None), (None, None)),
                                      'ref': ((None, None), (None, None), (None, None))},
                        'mir_coords': {'tra': ((None, None), (None, None), (None, None)),
                                       'ref': ((None, None), (None, None), (None, None))},
                        # 'ng_coords': {'tra': [[None, None], [None, None], [None, None]],
                        #               'ref': [[None, None], [None, None], [None, None]]},
                        # 'mir_coords': {'tra': [[None, None], [None, None], [None, None]],
                        #                'ref': [[None, None], [None, None], [None, None]]},
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


    #### Pulls the settings from the previous scale level ####
    def pullSettings(self, all=True):
        logger.critical("\n\nPulling settings...\n")
        if self.level == self.coarsest_scale_key():
            cfg.mw.err("Cannot pull SWIM settings from a coarser resolution level. \n"
                         "This is the coarsest resolution level.")
            return

        if not self.is_alignable():
            cfg.mw.err("Cannot pull SWIM settings until lower resolution levels are aligned.")
            return

        levels = self.levels
        cur_level = self.level
        prev_level = levels[levels.index(cur_level) + 1]
        cfg.mw.tell(f'Propagating SWIM settings from resolution level {prev_level} to {cur_level}...')
        sf = int(self.lvl(prev_level) / self.lvl(cur_level))

        os = self['level_data'][cur_level]['output_settings']
        os.update(copy.deepcopy(self['level_data'][prev_level]['output_settings']))

        mp = self['level_data'][cur_level]['method_presets'] # method presets, cur level
        mp.update(copy.deepcopy(self['level_data'][prev_level]['method_presets']))
        mp['grid']['size_1x1'][0] *= sf
        mp['grid']['size_2x2'][1] *= sf
        mp['manual'] = copy.deepcopy(self['level_data'][prev_level]['method_presets']['manual'])
        # mp['manual']['size'] *= sf

        defaults = self['level_data'][self.level]['defaults']
        defaults.update(copy.deepcopy(self['level_data'][prev_level]['defaults']))
        defaults['method_opts']['size_1x1'][0] *= sf
        defaults['method_opts']['size_1x1'][1] *= sf
        defaults['method_opts']['size_2x2'][0] *= sf
        defaults['method_opts']['size_2x2'][1] *= sf


        if all:
            indexes = list(range(len(self)))
        else:
            indexes = [self.zpos]
        try:
            for i in indexes:
                prev_settings = copy.deepcopy(self._data['stack'][i]['levels'][prev_level]['swim_settings'])
                prev_settings.pop('level')
                prev_settings.pop('init_afm')
                prev_settings.pop('img_size')
                prev_settings.pop('is_refinement')
                self['stack'][i]['levels'][cur_level]['swim_settings'] = prev_settings
                ss = self['stack'][i]['levels'][cur_level]['swim_settings']
                # ss = copy.deepcopy(prev_settings)
                # d['levels'][cur_level]['swim_settings']['img_size'] = self['images']['size_xy'][cur_level]

                ss['level'] = cur_level
                ss['img_size'] = self.image_size(cur_level)
                ss['is_refinement'] = self.isRefinement(level=cur_level)
                mo = ss['method_opts']
                method = mo['method']
                if method == 'grid':
                    mo['size_1x1'][0] *= sf
                    mo['size_1x1'][1] *= sf
                    mo['size_2x2'][0] *= sf
                    mo['size_2x2'][1] *= sf
                try:
                    init_afm = copy.deepcopy(self.afm(s=prev_level, l=i))
                except:
                    print_exception(extra=f'Section #{i}. Using identity instead...')
                    init_afm = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()
                try:
                    init_afm[0][2] *= sf
                    init_afm[1][2] *= sf
                except Exception as e:
                    logger.warning(f"[{i}] No valid aligntment data for {prev_level}. Reason: {e.__class__.__name__}")
                    cfg.mw.warn(f"During propagation of {prev_level} to {self.level},"
                                   f" previous data was missing for index {i}. It will be set to "
                                   f"identity matrix until a valid affine is propagated.")
                ss['init_afm'] = init_afm

        except Exception as e:
            cfg.mw.warn(f"Unable to propagate settings. Reason: {e.__class__.__name__}")
        else:
            self['level_data'][cur_level]['alignment_ready'] = True
            cfg.mw.hud.done()


    def initializeStack(self, data_location, images_location, images_info):
        logger.critical(f"Initializing data model...")

        levels = natural_sort(images_info['levels'])
        paths = natural_sort(images_info['paths'])
        top_level = levels[0]
        bottom_level = levels[-1]
        identity_matrix = np.array([[1., 0., 0.], [0., 1., 0.]]).tolist()

        self._data.update(
            info={
                'images_path': path_to_str(images_location),
                'file_path': path_to_str(data_location),
                'version': cfg.VERSION,
                'created': date_time(),
                'system': platform.system(),
                'node': platform.node(),
                'alignment_uuid': str(uuid.uuid4()),
                'series_uuid': images_info['uuid']
            },
            images=images_info,
            stack=[],
            # defaults={'levels': {v: {} for v in self.levels}},
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
                'level': bottom_level,
                'z_position': 0,
                'padlock': False,
                'current_tab': 0,
                'gif_speed': 100,
                'zarr_viewing': 'raw',
                'viewer_quality': bottom_level,
                'neuroglancer': {
                    'layout': '4panel',
                    'zoom': 1.0,
                    'blink': False,
                    'show_controls': False,
                    'show_bounds': False,
                    'show_axes': True,
                    'show_scalebar': True,
                    'region_selection': {
                        'select_by': 'cycle',  # cycle, zigzag, or sticky
                    }
                },
                'tra_ref_toggle': 'tra',
                'targ_karg_toggle': 1,
                'annotate_match_signals': True,
            },
            rendering={
                'normalize': [1, 255],
                'brightness': 0,
                'contrast': 0,
                'shader':
                    '''
                    #uicontrol vec3 color color(default="white")
                    #uicontrol float brightness slider(min=-1, max=1, step=0.01)
                    #uicontrol float contrast slider(min=-1, max=1, step=0.01)
                    void main() { emitRGB(color * (toNormalized(getDataValue()) + brightness) * exp(contrast));}
                    '''
            },
            protected = {
                'results': {},
            },
        )

        for i in range(len(paths)):
            basename = os.path.basename(paths[i])
            self['stack'].append({})
            self['stack'][i].update(
                index=i,
                name=basename,
                # file_path=paths[i], #1111-
                levels={s: {} for s in levels},
                # levels={bottom_level: {}},
                notes=''
            )
            for level in levels:
                self['stack'][i]['levels'][level].update(
                    initialized=False,
                    cafm=identity_matrix,
                    cafm_inv=identity_matrix,
                    swim_settings={
                        'index': i,
                        'name': basename,
                        'level': level,
                        'include': True,
                        'is_refinement': self.isRefinement(level=level),
                        'img_size': self['images']['size_xy'][level],
                        'init_afm': identity_matrix,
                    },
                    points={},
                    results={
                        'snr': 0.0,
                        'snr_std_deviation': 0.0,
                        'snr_mean': 0.0,
                        'affine_matrix': identity_matrix,
                    }
                )

        swim_presets = self.getSwimPresets()
        method_presets = self.getMethodPresets()

        for level in levels:
            self['level_data'][level].update(
                defaults={},
                zarr_made=False,
                chunkshape=self.get_transforming_chunkshape(level),
                initial_snr=None,
                aligned=False,
                alignment_ready=(level == self.coarsest_scale_key()),
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
            self.linkReference(s=level)

            self['level_data'][level]['defaults'].update(copy.deepcopy(swim_presets), method_opts=copy.deepcopy(
                method_presets[level]['grid']))

            self['level_data'][level].update(
                # Todo output preferences will need to propagate
                swim_presets=swim_presets,
                method_presets=method_presets[level],
            )

            for i in range(len(self)):
                self['stack'][i]['levels'][level]['swim_settings'].update(
                    copy.deepcopy(swim_presets),
                    method_opts=copy.deepcopy(method_presets[level]['grid']),
                )


    def save(self, silently=False):
        clr = inspect.stack()[1].function
        p = self.data_file_path
        if hasattr(self, 'ht'):
            if type(self.ht) == Cache:
                try:
                    self.ht.pickle()
                except Exception as e:
                    print_exception()
                    cfg.mw.warn(f"[{clr}] Cache failed to save; this is not fatal. Reason: {e.__class__.__name__}")
            else:
                logger.warning("Creating a new cache table")
                self.ht = Cache(self)
        try:
            if not silently:
                cfg.mw.tell(f"Saving '{p}'...")
                logger.critical(f"[{clr}]\nSaving >> '{p}'")
            try:
                write('json')(p, self._data)
            except:
                if not silently:
                    cfg.mw.err(f"[{clr}] Unable to save to file. Reason: {e.__class__.__name__}")
                print_exception()
            else:
                if not silently:
                    cfg.mw.hud.done()
                    logger.info(f"Save successful!")

        except Exception as e:
            print_exception()
            logger.critical(f"Error Saving: {p} !!")
            cfg.mw.err(f"[{clr}] Unable to save to file. Reason: {e.__class__.__name__}")
        else:
            logger.info(f"Save successful!")

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

# def dict_hash(dictionary: Dict[str, Any]) -> str:
#     """Returns an MD5 hash of a Python dictionary. source:
#     www.doc.ic.ac.uk/~nuric/coding/how-to-hash-a-dictionary-in-python.html"""
#     dhash = hashlib.md5()
#     encoded = json.dumps(dictionary, sort_keys=True).encode()
#     dhash.update(encoded)
#     return dhash.hexdigest()


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


'''
except Exception as e:
    logger.warning(f"[{l}] . Reason: {e.__class__.__name__}")

'''

if __name__ == '__main__':
    data = DataModel()
    print('Data Model Version: ' + str(data['version']))
    print(data)
