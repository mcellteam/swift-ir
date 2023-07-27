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
import platform
import statistics
from glob import glob
from copy import deepcopy
from heapq import nsmallest
from operator import itemgetter
from datetime import datetime
from dataclasses import dataclass
from functools import cache, cached_property
from functools import reduce
import numpy as np

from src.data_structs import data_template, layer_template
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

def time():
    return datetime.now().strftime('%Y-%m-%d_%H-%M-%S')


class DataModel:

    """ Encapsulate datamodel dictionary and wrap with methods for convenience """
    def __init__(self, data=None, name=None, quietly=False, mendenhall=False):
        self._current_version = cfg.VERSION
        if not quietly:
            logger.info('>>>> __init__ >>>>')
        if data:
            self._data = data  # Load project data from file
        else:
            self._data = copy.deepcopy(data_template)  # Initialize new project data
            self._data['created'] = time()
            self.set_system_info()
        if not quietly:
            self._data['modified'] = time()
        if name:
            self._data['data']['destination_path'] = name
        self._data['data']['mendenhall'] = mendenhall
        self._data['version'] = cfg.VERSION

        # self.zpos = self._data['data']['z_position']
        if not quietly:
            logger.info('<<<< __init__ <<<<')

    def __iter__(self):
        for item in self['data']['scales'][self.scale]['stack'][self.zpos]:
            yield item

    def __call__(self):
        return self.stack()

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
            return len(self._data['data']['scales']['scale_1']['stack'])
        except:
            logger.warning('No Images Found')

    # def loc(self):
    #     return self._data['data']['scales'][self.scale_key]['stack']

    def to_file(self):
        path = os.path.join(self.dest(), 'state_' + time() + '.swiftir')
        with open(path, 'w') as f:
            f.write(str(self.to_json()))


    @property
    def created(self):
        return self._data['created']

    @created.setter
    def created(self, val):
        self._data['created'] = val

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
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        # self._data['data']['Current Section (Index)'] = index
        if int(index) in range(0, len(self)):
            self['data']['z_position'] = int(index)
        else:
            logger.warning(f'\n\nINDEX OUT OF RANGE: {index} [caller: {inspect.stack()[1].function}]\n')

    @property
    def cname(self) -> str:
        '''Returns the default Zarr cname/compression type as a string.'''
        return self._data['data']['cname']

    @cname.setter
    def cname(self, x:str):
        self._data['data']['cname'] = str(x)

    @property
    def clevel(self) -> int:
        '''Returns the default Zarr clevel/compression level as an integer.'''
        return int(self._data['data']['clevel'])

    @clevel.setter
    def clevel(self, x:int):
        self._data['data']['clevel'] = int(x)

    @property
    def chunkshape(self) -> tuple:
        '''Returns the  default chunk shape tuple.'''
        return self._data['data']['chunkshape']

    @chunkshape.setter
    def chunkshape(self, x:tuple):
        self._data['data']['chunkshape'] = x

    # def chunkshape(self):
    #     try:
    #         return tuple(self._data['data']['chunkshape'])
    #     except:
    #         logger.warning('chunkshape not in dictionary')

    # #Deprecated
    # @property
    # def layer(self):
    #     '''Returns the Current Layer as an Integer.'''
    #     return self._data['data']['z_position']
    #
    # # Deprecated
    # @layer.setter
    # def layer(self, index):
    #     self._data['data']['z_position'] = index

    @property
    def brightness(self):
        return self._data['rendering']['brightness']

    @brightness.setter
    def brightness(self, val):
        self._data['rendering']['brightness'] = val

    @property
    def contrast(self):
        return self._data['rendering']['contrast']

    @contrast.setter
    def contrast(self, val):
        self._data['rendering']['contrast'] = val

    @property
    def scale_key(self):
        return self._data['data']['current_scale']

    @scale_key.setter
    def scale_key(self, str):
        self._data['data']['current_scale'] = str

    @property
    def scale(self):
        return self._data['data']['current_scale']

    @scale.setter
    def scale(self, str):
        self._data['data']['current_scale'] = str

    @property
    def current_method(self):
        # caller = inspect.stack()[1].function
        # logger.info(f'caller: {caller}')
        # self._data['data']['scales'][self.scale_key]['stack'][self.zpos].setdefault('current_method', 'grid-default')
        try:
            return self._data['data']['scales'][self.scale]['stack'][self.zpos]['current_method']
        except:
            print_exception()
            self._data['data']['scales'][self.scale]['stack'][self.zpos]['current_method'] = 'grid-default'
            return self._data['data']['scales'][self.scale]['stack'][self.zpos]['current_method']

    @current_method.setter
    def current_method(self, str):
        # self._data['data']['scales'][self.scale_key]['stack'][self.zpos]['current_method'] = str
        # for s in self.scales():
        for s in self.finer_scales():
            self._data['data']['scales'][s]['stack'][self.zpos]['current_method'] = str


    def get_current_method(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['current_method']

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
    def grid_default_regions(self):
        return self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['swim_settings']['grid_default_regions']

    @grid_default_regions.setter
    def grid_default_regions(self, lst):
        self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['swim_settings']['grid_default_regions'] = lst

    @property
    def grid_custom_regions(self):
        return self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['swim_settings']['grid-custom-regions']

    def get_grid_custom_regions(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['alignment']['swim_settings'][
            'grid-custom-regions']

    @grid_custom_regions.setter
    def grid_custom_regions(self, lst):
        # for s in self.scales():
        for s in self.finer_scales():
            self._data['data']['scales'][s]['stack'][self.zpos]['alignment']['swim_settings']['grid-custom-regions'] = lst

    @property
    def karg(self):
        return self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['karg']

    @karg.setter
    def karg(self, use):
        self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['karg'] = use

    @property
    def targ(self):
        return self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['targ']

    @targ.setter
    def targ(self, use):
        self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['targ'] = use

    @property
    def default_poly_order(self):
        return self._data['data']['defaults']['corrective-polynomial']

    @default_poly_order.setter
    def default_poly_order(self, use):
        self._data['data']['defaults']['corrective-polynomial'] = use


    @property
    def default_whitening(self):
        return self._data['data']['defaults']['signal-whitening']

    @default_whitening.setter
    def default_whitening(self, x):
        self._data['data']['defaults']['signal-whitening'] = x

    @property
    def defaults(self):
        return self._data['data']['defaults']

    @property
    def defaults_pretty(self):
        d = self._data['data']['defaults']
        defaults_str = ''
        nl = '\n'
        defaults_str += f"Bounding Box: {d['bounding-box']}\n" \
                        f"Corrective Polynomial: {d['corrective-polynomial']}\n" \
                        f"Initial Rotation: {d['initial-rotation']}\n" \
                        f"SWIM Window Dimensions:\n{nl.join(['  %s: %s' % (s.ljust(9), '%sx%s' % tuple(d[s]['swim-window-px'])) for s in self.scales()])}\n" \
                        f"SWIM iterations: {d['swim-iterations']}\n" \
                        f"SWIM Signal Whitening: {d['signal-whitening']}"
        return defaults_str

    # layer['alignment']['swim_settings'].setdefault('karg', False)

    @property
    def count(self):
        return len(self)

    def section(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]


    # def set_fullscale_settings(self):


    def get_ref_index(self, l=None):
        if l == None: l = self.zpos
        caller = inspect.stack()[1].function
        # logger.critical(f'caller: {caller}, l={l}')
        if self.skipped(s=self.scale, l=l):
            return self.get_index(self._data['data']['scales'][self.scale]['stack'][l]['filename']) #Todo refactor this but not sure how
        reference = self._data['data']['scales'][self.scale]['stack'][l]['reference']
        if reference == '':
            return self.get_index(self._data['data']['scales'][self.scale]['stack'][l]['filename'])
        else:
            return self.get_index(reference)

    # @cache
    def is_aligned(self, s=None):
        caller = inspect.stack()[1].function
        # logger.critical(f' is_aligned caller: {caller} >>>> ')
        if s == None: s = self.scale
        snr_list = self.snr_list(s=s)
        if sum(snr_list) < 1:
            # logger.info(f'is_aligned [{s}] is returning False (sum of SNR list is < 1)')
            return False
        else:
            # logger.info(f'is_aligned [{s}] is returning True (sum of SNR list > 1)')
            return True

    def is_alignable(self) -> bool:
        '''Checks if the current scale_key is able to be aligned'''
        # logger.info('')
        try:
            scales_list = self.scales()
            cur_scale_key = self.scale
            coarsest_scale = scales_list[-1]
            if cur_scale_key == coarsest_scale:
                # logger.info("is cur scale_key alignable? returning True")
                return True

            cur_scale_index = scales_list.index(cur_scale_key)
            next_coarsest_scale_key = scales_list[cur_scale_index + 1]
            if not self.is_aligned(s=next_coarsest_scale_key):
                # logger.critical(f"is {self.scale_key} alignable? False because previous scale_key is not aligned")
                return False
            else:
                # logger.critical(f'is {self.scale_key} alignable? Returning True')
                return True
        except:
            print_exception()

    def is_aligned_and_generated(self, s=None) -> bool:
        if s == None: s = self.scale
        #Todo improve this, cache it or something

        # if s in get_scales_with_generated_alignments(self.scales()):
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
        return self._data['data']['benchmarks']['t_scaling']

    @t_scaling.setter
    def t_scaling(self, dt):
        self._data['data']['benchmarks']['t_scaling'] = dt

    @property
    def t_scaling_convert_zarr(self):
        return self._data['data']['benchmarks']['t_scaling_convert_zarr']

    @t_scaling_convert_zarr.setter
    def t_scaling_convert_zarr(self, dt):
        self._data['data']['benchmarks']['t_scaling_convert_zarr'] = dt

    @property
    def t_thumbs(self):
        return self._data['data']['benchmarks']['t_thumbs']

    @t_thumbs.setter
    def t_thumbs(self, dt):
        self._data['data']['benchmarks']['t_thumbs'] = dt

    @property
    def t_align(self):
        return self._data['data']['benchmarks']['scales'][self.scale]['t_align']

    @t_align.setter
    def t_align(self, dt):
        self._data['data']['benchmarks']['scales'][self.scale]['t_align'] = dt

    @property
    def t_generate(self):
        return self._data['data']['benchmarks']['scales'][self.scale]['t_generate']

    @t_generate.setter
    def t_generate(self, dt):
        self._data['data']['benchmarks']['scales'][self.scale]['t_generate'] = dt

    @property
    def t_convert_zarr(self):
        return self._data['data']['benchmarks']['scales'][self.scale]['t_convert_zarr']

    @t_convert_zarr.setter
    def t_convert_zarr(self, dt):
        self._data['data']['benchmarks']['scales'][self.scale]['t_convert_zarr'] = dt

    @property
    def t_thumbs_aligned(self):
        return self._data['data']['benchmarks']['scales'][self.scale]['t_thumbs_aligned']

    @t_thumbs_aligned.setter
    def t_thumbs_aligned(self, dt):
        self._data['data']['benchmarks']['scales'][self.scale]['t_thumbs_aligned'] = dt

    @property
    def t_thumbs_spot(self):
        return self._data['data']['benchmarks']['scales'][self.scale]['t_thumbs_spot']

    @t_thumbs_spot.setter
    def t_thumbs_spot(self, dt):
        self._data['data']['benchmarks']['scales'][self.scale]['t_thumbs_spot'] = dt

    def set_thumb_scaling_factor_source(self, factor:int):
        self._data['data']['thumb_scaling_factor_source'] = factor

    def set_thumb_scaling_factor_aligned(self, factor:int, s:str):
        self._data['data']['scales'][s]['thumb_scaling_factor_aligned'] = factor

    def set_thumb_scaling_factor_corr_spot(self, factor:int, s:str):
        self._data['data']['scales'][s]['thumb_scaling_factor_corr_spot'] = factor

    def normalize(self):
        return self._data['rendering']['normalize']

    def set_normalize(self, range):
        self._data['rendering']['normalize'] = range

    def notes(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['notes']


    def save_notes(self, text, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        self._data['data']['scales'][s]['stack'][l]['notes'] = text

    def sl(self):
        return (self.scale, self.zpos)

    def to_json(self):
        return json.dumps(self._data)

    def to_dict(self):
        return self._data

    def dest(self) -> str:
        return self._data['data']['destination_path']

    def name(self) -> str:
        return os.path.split(self.dest())[-1]

    def set_system_info(self):
        logger.info('')
        try:    self._data['system']['node'] = platform.node()
        except: self._data['system']['node'] = 'Unknown'

    def base_image_name(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # logger.info(f'Caller: {inspect.stack()[1].function}, s={s}, l={l}')
        return os.path.basename(self._data['data']['scales'][s]['stack'][l]['filename'])

    '''NEW METHODS USING NEW DATA SCHEMA 2023'''

    def filename(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['filename']

    def reference(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['reference']

    def has_reference(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        r = self._data['data']['scales'][s]['stack'][l]['reference']
        f = self._data['data']['scales'][s]['stack'][l]['filename']
        if r == '':
            return False
        if r == f:
            return False
        return True

    def filename_basename(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.basename(self._data['data']['scales'][s]['stack'][l]['filename'])

    def reference_basename(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.basename(self._data['data']['scales'][s]['stack'][l]['reference'])

    '''END OF NEW METHODS'''

    def filenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.abspath(l['filename'])
                for l in self._data['data']['scales'][self.scales()[0]]['stack']])

    def basefilenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.basename(l['filename'])
                for l in self._data['data']['scales'][self.scales()[0]]['stack']])

    def thumbnail(self, l = None):
        '''Returns absolute path of thumbnail for current layer '''
        if l == None: l = self.zpos
        return self.thumbnails()[l]

    def thumbnails(self) -> list:
        lst = []
        for name in self.basefilenames():
            lst.append(os.path.join(self.dest(), 'thumbnails', name))
        return lst


    def thumbnail_ref(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.join(self.dest(), 'thumbnails', os.path.basename(self._data['data']['scales'][s]['stack'][l]['reference']))


    def thumbnail_tra(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.join(self.dest(), 'thumbnails', os.path.basename(self._data['data']['scales'][s]['stack'][l]['filename']))

    def thumbnail_aligned(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        '''Returns absolute path of thumbnail for current layer '''
        return os.path.join(self.dest(), self.scale, 'thumbnails_aligned', self.filename_basename(s=s,l=l))

    def thumbnails_ref(self) -> list:
        paths = []
        for l in self.stack():
            paths.append(os.path.join(self.dest(), 'thumbnails', os.path.basename(l['reference'])))
        return paths

    def thumbnails_aligned(self) -> list:
        paths = []
        for layer in range(0, len(self)):
            paths.append(os.path.join(self.dest(), self.scale, 'thumbnails_aligned', self.base_image_name(l=layer)))
        return paths



    # def corr_signal_path(self, i, s=None, l=None):
    #     if s == None: s = self.scale_key
    #     if l == None: l = self.zpos
    #     img = self.base_image_name(s=s, l=l)
    #     return os.path.join(self.dest(), s, 'signals' , 'corr_spot_%d_' %i + img)


    def signals_q0(self) -> list:
        names = []
        for i, img in enumerate(self.basefilenames()):
            filename, extension = os.path.splitext(img)
            method = self._data['data']['scales'][self.scale]['stack'][i]['current_method']
            names.append(os.path.join(self.dest(), self.scale, 'signals' , '%s_%s_0%s'% (filename,method,extension)))
        return names

    def signals_q1(self) -> list:
        names = []
        for i, img in enumerate(self.basefilenames()):
            filename, extension = os.path.splitext(img)
            method = self._data['data']['scales'][self.scale]['stack'][i]['current_method']
            names.append(os.path.join(self.dest(), self.scale, 'signals' , '%s_%s_1%s'% (filename,method,extension)))
        return names

    def signals_q2(self) -> list:
        names = []
        for i, img in enumerate(self.basefilenames()):
            filename, extension = os.path.splitext(img)
            method = self._data['data']['scales'][self.scale]['stack'][i]['current_method']
            names.append(os.path.join(self.dest(), self.scale, 'signals' , '%s_%s_2%s'% (filename,method,extension)))
        return names

    def signals_q3(self) -> list:
        names = []
        for i, img in enumerate(self.basefilenames()):
            filename, extension = os.path.splitext(img)
            method = self._data['data']['scales'][self.scale]['stack'][i]['current_method']
            names.append(os.path.join(self.dest(), self.scale, 'signals' , '%s_%s_3%s'% (filename,method,extension)))
        return names

    def clobber(self):
        return self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['swim_settings']['clobber_fixed_noise']

    def set_clobber(self, b, l=None, glob=False):
        if l == None: l = self.zpos
        # for s in self.scales():
        for s in self.finer_scales():
            if glob:
                for i in range(len(self)):
                    self._data['data']['scales'][s]['stack'][i]['alignment']['swim_settings']['clobber_fixed_noise'] = b
            else:
                self._data['data']['scales'][s]['stack'][l]['alignment']['swim_settings']['clobber_fixed_noise'] = b

    def clobber_px(self):
        return self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['swim_settings']['clobber_fixed_noise_px']

    def set_clobber_px(self, x, l=None, glob=False):
        if l == None: l = self.zpos
        # for s in self.scales():
        for s in self.finer_scales():
            if glob:
                for i in range(len(self)):
                    self._data['data']['scales'][s]['stack'][i]['alignment']['swim_settings']['clobber_fixed_noise_px'] = x
            else:
                self._data['data']['scales'][s]['stack'][l]['alignment']['swim_settings']['clobber_fixed_noise_px'] = x


    def get_signals_filenames(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        dir = os.path.join(self.dest(), s, 'signals')
        basename = os.path.basename(self.base_image_name(s=s, l=l))
        filename, extension = os.path.splitext(basename)
        paths = os.path.join(dir, '%s_%s_*%s' % (filename, self.current_method, extension))
        names = glob(paths)
        # logger.info(f'Search Path: {paths}\nReturning: {names}')
        return natural_sort(names)

    def get_grid_custom_filenames(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        dir = os.path.join(self.dest(), s, 'signals')
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
        return natural_sort(self._data['data']['scales'].keys())[-1]

    def layer_dict(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]

    def first_cafm_false(self):
        for l in range(len(self)):
            if not self.cafm_hash_comports(l=l):
                logger.info(f'returning {l}')
                return l
            # if not self._data['data']['scales'][self.scale_key]['stack'][l]['cafm_comports']:
            #     return l


        return None




    def set_defaults(self):
        logger.info(f'[{inspect.stack()[1].function}] Setting Defaults')

        initial_zpos = int(len(self)/2)
        self._data['data']['zposition'] = initial_zpos

        self._data.setdefault('developer_mode', cfg.DEV_MODE)
        self._data.setdefault('data', {})
        self._data.setdefault('rendering', {})
        self._data.setdefault('state', {})
        self._data.setdefault('system', {})
        # self._data['system'].setdefault('max_processors', cfg.TACC_MAX_CPUS)
        # self._data['system'].setdefault('max_qtwebengine_threads', cfg.QTWEBENGINE_RASTER_THREADS)
        # self._data['system'].setdefault('recipe_logging', cfg.RECIPE_LOGGING)
        self._data['state'].pop('stage_viewer', None)
        self._data['state']['mode'] = 'stack-xy' # TEMPORARY FORCE
        self._data['state']['has_cal_grid'] = False
        # self._data['state'].setdefault('ng_layout', 'xy')
        self._data['state']['ng_layout'] = '4panel'
        self._data['state']['current_tab'] = 0
        self._data['state'].setdefault('blink', False)
        self._data['state'].setdefault('tool_windows', {})
        # Set default to value from user preferences... Todo: all user preferences should work this way
        try:
            self._data['state'].setdefault('neutral_contrast', getOpt('neuroglancer,NEUTRAL_CONTRAST_MODE'))
        except:
            self._data['state'].setdefault('neutral_contrast',True)
            print_exception()

        try:
            self._data['state'].setdefault('show_yellow_frame', getOpt('neuroglancer,SHOW_YELLOW_FRAME'))
        except:
            self._data['state'].setdefault('show_yellow_frame',True)
            print_exception()

        try:
            self._data['state'].setdefault('show_axis_lines', getOpt('neuroglancer,SHOW_AXIS_LINES'))
        except:
            self._data['state'].setdefault('show_axis_lines',True)
            print_exception()

        try:
            self._data['state'].setdefault('show_ng_controls', getOpt('neuroglancer,SHOW_UI_CONTROLS'))
        except:
            self._data['state'].setdefault('show_ng_controls',True)
            print_exception()

        # logger.critical(str(self._data['state']))

        # self._data['state'].setdefault('auto_update_ui', True)
        # self._data['state'].setdefault('MA_focus', None) #0 = L, 1 = R
        # self._data['state'].setdefault('focus_widget', None)
        self._data['state']['tra_ref_toggle'] = 1 #Force
        self._data['state']['targ_karg_toggle'] = 1 #Force
        self._data['state']['tool_windows'].setdefault('python',False)
        self._data['state']['tool_windows'].setdefault('notes',False)
        self._data['state']['tool_windows'].setdefault('hud',False)
        # self._data['state']['tool_windows'].setdefault('flicker',False)
        self._data['state']['tool_windows'].setdefault('signals',True)
        self._data['state']['tool_windows'].setdefault('raw_thumbnails',True)
        self._data['state']['tool_windows'].setdefault('matches',True)
        self._data['state']['tool_windows'].setdefault('snr_plot',False)
        self._data['data'].setdefault('shader', cfg.SHADER)
        self._data['data'].setdefault('cname', cfg.CNAME)
        self._data['data'].setdefault('clevel', cfg.CLEVEL)
        # self._data['data'].setdefault('autoalign_flag', False)
        self._data['data'].setdefault('autoalign_flag', True)
        self._data['data'].setdefault('chunkshape', (cfg.CHUNK_Z, cfg.CHUNK_Y, cfg.CHUNK_X))
        self._data['data'].setdefault('benchmarks', {})
        self._data['data']['benchmarks'].setdefault('t_scaling', 0.0)
        self._data['data']['benchmarks'].setdefault('t_scaling_convert_zarr', 0.0)
        self._data['data']['benchmarks'].setdefault('t_thumbs', 0.0)
        self._data['data']['benchmarks'].setdefault('scales', {})
        self._data['data'].setdefault('t_scaling', 0.0)
        self._data['data'].setdefault('t_scaling_convert_zarr', 0.0)
        self._data['data'].setdefault('t_thumbs', 0.0)
        self._data['data'].setdefault('defaults', {})
        self._data['data']['defaults'].setdefault('signal-whitening', cfg.DEFAULT_WHITENING)
        self._data['data']['defaults'].setdefault('bounding-box', cfg.DEFAULT_BOUNDING_BOX)
        self._data['data']['defaults'].setdefault('corrective-polynomial', cfg.DEFAULT_CORRECTIVE_POLYNOMIAL)
        self._data['data']['defaults'].setdefault('initial-rotation', cfg.DEFAULT_INITIAL_ROTATION)
        self._data['data']['defaults'].setdefault('swim-iterations', cfg.DEFAULT_SWIM_ITERATIONS)
        self._data['data']['defaults'].setdefault('scales', {})
        self._data['rendering'].setdefault('normalize', [1,255])
        self._data['rendering'].setdefault('brightness', 0)
        self._data['rendering'].setdefault('contrast', 0)
        self._data['rendering'].setdefault('shader', '''
        #uicontrol vec3 color color(default="white")
        #uicontrol float brightness slider(min=-1, max=1, step=0.01)
        #uicontrol float contrast slider(min=-1, max=1, step=0.01)
        void main() { emitRGB(color * (toNormalized(getDataValue()) + brightness) * exp(contrast));}
        ''')

        for s in self.scales():
            logger.info('Setting defaults for %s' % self.scale_pretty(s=s))
            scale = self._data['data']['scales'][s]
            scale.setdefault('stack', []) #0725+
            scale.setdefault('use_bounding_rect', cfg.DEFAULT_BOUNDING_BOX)
            scale.setdefault('has_bounding_rect', cfg.DEFAULT_BOUNDING_BOX) #0512+
            scale.setdefault('resolution', (cfg.DEFAULT_RESZ, cfg.DEFAULT_RESY, cfg.DEFAULT_RESX))
            self._data['data']['benchmarks']['scales'].setdefault(s, {})
            self._data['data']['benchmarks']['scales'][s].setdefault('t_align', 0.0)
            self._data['data']['benchmarks']['scales'][s].setdefault('t_generate', 0.0)
            self._data['data']['benchmarks']['scales'][s].setdefault('t_convert_zarr', 0.0)
            self._data['data']['benchmarks']['scales'][s].setdefault('t_thumbs_aligned', 0.0)
            self._data['data']['benchmarks']['scales'][s].setdefault('t_thumbs_spot', 0.0)
            # self._data['data']['benchmarks']['scales'][s].setdefault('thumb_scaling_factor_aligned', 0.0)
            self._data['data']['defaults']['scales'].setdefault(s, {})
            if s == self.coarsest_scale_key():
                self._data['data']['scales'][s]['isRefinement'] = False
            else:
                self._data['data']['scales'][s]['isRefinement'] = True



            for i in range(len(self)):
                layer = scale['stack'][i]

                layer.setdefault('current_method', 'grid-default')
                layer.setdefault('selected_method', 'grid-default')
                layer.setdefault('data_comports', True)
                layer.setdefault('needs_propagation', False)
                layer.setdefault('alignment_hash', '')
                layer.setdefault('cafm_alignment_hash', None)

                layer.setdefault('alignment_history', {})
                layer['alignment_history'].setdefault('grid-default', {})
                layer['alignment_history'].setdefault('grid-custom', {})
                layer['alignment_history'].setdefault('manual-hint', {})
                layer['alignment_history'].setdefault('manual-strict', {})

                if type(layer['alignment_history']['grid-default']) == list:
                    layer['alignment_history']['grid-default'] = {}
                if type(layer['alignment_history']['grid-custom']) == list:
                    layer['alignment_history']['grid-custom'] = {}
                if type(layer['alignment_history']['manual-hint']) == list:
                    layer['alignment_history']['manual-hint'] = {}
                if type(layer['alignment_history']['manual-strict']) == list:
                    layer['alignment_history']['manual-strict'] = {}


                layer['alignment_history']['grid-default'].setdefault('snr', 0.0)
                layer['alignment_history']['grid-custom'].setdefault('snr', 0.0)
                layer['alignment_history']['manual-hint'].setdefault('snr', 0.0)
                layer['alignment_history']['manual-strict'].setdefault('snr', 0.0)

                # report = 'SNR: 0.0 (+-0.0 n:1)  <0.0  0.0>'
                layer['alignment_history']['grid-default'].setdefault('snr_report', 'SNR: --')
                layer['alignment_history']['grid-custom'].setdefault('snr_report', 'SNR: --')
                layer['alignment_history']['manual-hint'].setdefault('snr_report', 'SNR: --')
                layer['alignment_history']['manual-strict'].setdefault('snr_report', 'SNR: --')

                init_afm = [[1., 0., 0.], [0., 1., 0.]]
                layer['alignment_history']['grid-default'].setdefault('affine_matrix', init_afm)
                layer['alignment_history']['grid-custom'].setdefault('affine_matrix', init_afm)
                layer['alignment_history']['manual-hint'].setdefault('affine_matrix', init_afm)
                layer['alignment_history']['manual-strict'].setdefault('affine_matrix', init_afm)

                layer['alignment_history']['grid-default'].setdefault('cafm_hash', None)
                layer['alignment_history']['grid-custom'].setdefault('cafm_hash', None)
                layer['alignment_history']['manual-hint'].setdefault('cafm_hash', None)
                layer['alignment_history']['manual-strict'].setdefault('cafm_hash', None)

                # if not 'cumulative_afm' in layer['alignment_history'][cfg.data.get_current_method(l=i)]:
                #     layer['alignment_history']['grid-default']['cumulative_afm'] =

                # init_afm = [[1., 0., 0.], [0., 1., 0.]]
                # layer['alignment_history']['grid-default'].setdefault('affine_matrix', init_afm)
                # layer['alignment_history']['grid-custom'].setdefault('affine_matrix', init_afm)
                # layer['alignment_history']['manual-hint'].setdefault('affine_matrix', init_afm)
                # layer['alignment_history']['manual-strict'].setdefault('affine_matrix', init_afm)

                # if cfg.data.scale_key != cfg.data.coarsest_scale_key():
                #     for i, section in range(0, len(cfg.data)):
                #         scales = cfg.data.scales()
                #         scale_prev = scales[scales.index(scale_key) + 1]
                #         scale_prev_dict = cfg.data['data']['scales'][scale_prev]['stack']
                #         prev_method = scale_prev_dict[i]['current_method']
                #         scale_prev_dict[i]['alignment_history'].setdefault[prev_method]['affine_matrix']

                layer.setdefault('alignment', {})
                # layer['alignment'].setdefault('meta', {})
                layer['alignment']['meta'] = {} #<-- might be a good idea, to recreate this from scratch every time
                # layer['alignment']['meta'].setdefault('index', i)
                layer['alignment']['meta']['index'] = i
                layer['alignment'].setdefault('dev_mode', cfg.DEV_MODE)
                layer['alignment'].setdefault('swim_settings', {})
                # logger.critical(f"{os.path.join(self.dest(), s, 'tmp')}")
                # layer['alignment']['swim_settings']['karg_path'] = os.path.join(self.dest(), s, 'tmp')
                # layer['alignment']['swim_settings']['targ_path'] = os.path.join(self.dest(), s, 'tmp')
                layer['alignment']['swim_settings'].pop('karg_path', None)
                layer['alignment']['swim_settings'].pop('targ_path', None)
                layer['alignment']['swim_settings'].setdefault('clobber_fixed_noise', False)
                layer['alignment']['swim_settings'].setdefault('clobber_fixed_noise_px', cfg.DEFAULT_CLOBBER_PX)
                layer['alignment']['swim_settings'].setdefault('extra_kwargs', '')
                layer['alignment']['swim_settings'].setdefault('extra_args', '')
                layer['alignment']['swim_settings'].setdefault('use_logging', True)
                layer['alignment']['swim_settings'].setdefault('grid_default_regions', [1,1,1,1])
                layer['alignment']['swim_settings'].setdefault('grid-custom-regions', [1,1,1,1])
                layer['alignment']['swim_settings'].setdefault('iterations', cfg.DEFAULT_SWIM_ITERATIONS)
                layer['alignment']['swim_settings'].setdefault('signal-whitening', cfg.DEFAULT_WHITENING)
                layer['alignment']['swim_settings'].pop('karg', None)
                layer['alignment']['swim_settings'].pop('targ', None)
                layer['alignment'].setdefault('grid_custom_px_1x1', None)
                layer['alignment'].setdefault('grid_custom_px_2x2', None)
                layer['alignment'].setdefault('manual_swim_window_px', cfg.DEFAULT_MANUAL_SWIM_WINDOW)

                # layer['alignment']['swim_settings'].setdefault('signal-whitening', cfg.DEFAULT_WHITENING)
                if 'manual_settings' in layer['alignment'].keys():
                    if 'manual_swim_window_px' in layer['alignment']['manual_settings'].keys():
                        layer['alignment']['manual_swim_window_px'] = layer['alignment']['manual_settings']['manual_swim_window_px']
                        layer['alignment'].pop('manual_settings', None)


                if 'grid-custom-px' in layer['alignment']['swim_settings'].keys():
                    layer['alignment']['grid_custom_px_1x1'] = layer['alignment']['swim_settings']['grid-custom-px']
                    layer['alignment']['swim_settings'].pop('grid-custom-px', None)

                if 'grid-custom-2x2-px' in layer['alignment']['swim_settings'].keys():
                    layer['alignment']['grid_custom_px_2x2'] = layer['alignment']['swim_settings']['grid-custom-2x2-px']
                    layer['alignment']['swim_settings'].pop('grid-custom-2x2-px', None)


                # layer['alignment']['manual_settings'].setdefault('swim_whitening', cfg.DEFAULT_MANUAL_WHITENING)
                layer['alignment'].setdefault('manpoints', {})
                layer['alignment']['manpoints'].setdefault('ref', [])
                layer['alignment']['manpoints'].setdefault('base', [])
                layer['alignment'].setdefault('manpoints_mir', {})
                layer['alignment']['manpoints_mir'].setdefault('ref', [])
                layer['alignment']['manpoints_mir'].setdefault('base', [])
                if s == self.coarsest_scale_key():
                    layer['alignment'].setdefault('targ', True)
                    layer['alignment'].setdefault('karg', True)
                else:
                    layer['alignment'].setdefault('targ', False)
                    layer['alignment'].setdefault('karg', False)
                # layer['alignment'].setdefault('targ', True)
                # layer['alignment'].setdefault('karg', True)
        try:
            self.set_auto_swim_windows_to_default(s_list=self.scales())
            self.set_manual_swim_windows_to_default(s_list=self.scales())
        except:
            print_exception()


    def isRefinement(self):
        return  self._data['data']['scales'][self.scale]['isRefinement']

    def set_source_path(self, dir):
        # self._data['data']['src_img_root'] = dir
        self._data['data'].update({'source_path': dir})

    def source_path(self):
        return self._data['data']['source_path']

    def get_source_img_paths(self):
        imgs = []
        for f in self.filenames():
            imgs.append(os.path.join(self.source_path(), os.path.basename(f)))
        return imgs

    def is_mendenhall(self):
        return self._data['data']['mendenhall']

    def get_iter(self, s=None, start=0, end=None):
        if s == None: s = self.scale
        return ScaleIterator(self._data['data']['scales'][s]['stack'][start:end])

    def references_list(self):
        return [x['reference'] for x in self.get_iter()]

    def transforming_list(self):
        return [x['filename'] for x in self.get_iter()]

    def get_index(self, filename):
        # logger.info(f'[{inspect.stack()[1].function}] filename = {filename}')
        # logger.info(f'filename = {filename}')
        return self.transforming_list().index(filename)

    def get_ref_index_offset(self, l=None):
        if l == None:
            l = self.zpos
        return l - self.get_ref_index(l=l)

    def method_results(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return self._data['data']['scales'][s]['stack'][l][
                'alignment']['method_results']
        except:
            return {}

    def datetime(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return self._data['data']['scales'][s]['stack'][l][
                'alignment']['method_results']['datetime']
        except:
            return ''

    @property
    def timings(self):
        try:
            t0 = (f"%.1fs" % self['data']['benchmarks']['t_scaling']).rjust(12)
            t0m = (f"%.3fm" % (self['data']['benchmarks']['t_scaling'] / 60))
        except:
            t0 = t0m = "???"

        try:
            t1 = (f"%.1fs" % self['data']['benchmarks']['t_scaling_convert_zarr']).rjust(12)
            t1m = (f"%.3fm" % (self['data']['benchmarks']['t_scaling_convert_zarr'] / 60))
        except:
            t1 = t1m = "???"

        try:
            t2 = (f"%.1fs" % self['data']['benchmarks']['t_thumbs']).rjust(12)
            t2m = (f"%.3fm" % (self['data']['benchmarks']['t_thumbs'] / 60))
        except:
            t2 = t2m = "???"

        t3, t4, t5, t6 = {}, {}, {}, {}
        t3m, t4m, t5m, t6m = {}, {}, {}, {}
        for s in self.scales():
            try:
                t3[s] = (f"%.1fs" % self['data']['benchmarks']['scales'][s]['t_align']).rjust(12)
                t3m[s] = (f"%.3fm" % (self['data']['benchmarks']['scales'][s]['t_align'] / 60))
            except:
                t3[s] = t3m[s] = "???"

            try:
                t4[s] = (f"%.1fs" % self['data']['benchmarks']['scales'][s]['t_convert_zarr']).rjust(12)
                t4m[s] = (f"%.3fm" % (self['data']['benchmarks']['scales'][s]['t_convert_zarr'] / 60))
            except:
                t4[s] = t4m[s] = "???"

            try:
                t5[s] = (f"%.1fs" % self['data']['benchmarks']['scales'][s]['t_generate']).rjust(12)
                t5m[s] = (f"%.3fm" % (self['data']['benchmarks']['scales'][s]['t_generate'] / 60))
            except:
                t5[s] = t5m[s] = "???"

            try:
                t6[s] = (f"%.1fs" % self['data']['benchmarks']['scales'][s]['t_thumbs_aligned']).rjust(12)
                t6m[s] = (f"%.3fm" % (self['data']['benchmarks']['scales'][s]['t_thumbs_aligned'] / 60))
            except:
                t6[s] = t6m[s] = "???"

        timings = []
        timings.append(('Generate Scale Hierarchy', t0 + ' / ' + t0m))
        timings.append(('Convert All Scales to Zarr', t1 + ' / ' + t1m))
        timings.append(('Generate Source Image Thumbnails', t2 + ' / ' + t2m))

        timings.append(('Compute Affines', ''))
        for s in cfg.data.scales():
            timings.append(('  ' + cfg.data.scale_pretty(s), '%s / %s' % (t3[s], t3m[s])))
        timings.append(('Generate Aligned TIFFs', ''))
        for s in cfg.data.scales():
            timings.append(('  ' + cfg.data.scale_pretty(s), '%s / %s' % (t4[s], t4m[s])))
        timings.append(('Convert Aligned TIFFs to Zarr', ''))
        for s in cfg.data.scales():
            timings.append(('  ' + cfg.data.scale_pretty(s), '%s / %s' % (t5[s], t5m[s])))
        timings.append(('Generate Aligned TIFF Thumbnails', ''))
        for s in cfg.data.scales():
            timings.append(('  ' + cfg.data.scale_pretty(s), '%s / %s' % (t6[s], t6m[s])))
        return timings


    def previous_method_results(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return self._data['data']['scales'][s]['stack'][l][
                'alignment']['previous_method_results']
        except:
            return {}


    def get_method_data(self, method, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['alignment_history'][method]


    def snr(self, s=None, l=None, method=None) -> float:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        if method == None:
            method = self.method(s=s,l=l)
        # logger.critical('')
        # if l == 0:
        #     return 0.0
        try:
            # if method == None:
            #     method = self.current_method
            # components = self._data['data']['scales'][s]['stack'][l]['alignment_history'][method][-1]['snr']
            # components = self._data['data']['scales'][s]['stack'][l]['alignment']['method_results']['snr'] #prev
            components = self._data['data']['scales'][s]['stack'][l]['alignment_history'][method]['snr']
            '''
            13:55:45 WARNING [helpers.print_exception:731]   [20230526_13:55:45]
            Error Type : <class 'TypeError'>
            Error Value : list indices must be integers or slices, not str
            Traceback (most recent call last):
              File "/Users/joelyancey/swift-ir/src/data_model.py", line 918, in snr
                components = self._data['data']['scales'][s]['stack'][l]['alignment_history'][method]['snr']
            TypeError: list indices must be integers or slices, not str
            
            13:55:45 WARNING [data_model.snr:925] Unable to return SNR for layer #18
            
            '''

            # value = self.method_results(s=s, l=l)['snr']
            # return statistics.fmean(map(float, value))
            if type(components) == float:
                return components
            else:
                return statistics.fmean(map(float, components))
                # return statistics.fmean(components)
        except:
            # print_exception()
            # logger.warning('Unable to return SNR for layer #%d' %l)
            tstamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            exi = sys.exc_info()
            txt = f" [{tstamp}] Error Type/Value : {exi[0]} / {exi[1]}"
            logger.warning(f"{txt}\n[{l}] Unable to return SNR. Returning 0.0")
            return 0.0

    def snr_prev(self, s=None, l=None) -> float:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        if l == 0:
            return 0.0
        try:
            value = self.previous_method_results(s=s, l=l)['snr']
            return statistics.fmean(map(float, value))
        except:
            # print_exception()
            return 0.0


    def snr_list(self, s=None) -> list[float]:
        try:
            return [self.snr(s=s, l=i) for i in range(len(self))]
        except:
            logger.warning(f'No SNR Data Found. Returning 0s List [caller: {inspect.stack()[1].function}]...')
            print_exception()
            return [0] * len(self)


    def snr_prev_list(self, s=None, l=None):
        # logger.info('caller: %s' % inspect.stack()[1].function)
        if s == None: s = self.scale
        try:
            return [self.snr_prev(s=s, l=i) for i in range(len(self))]
        except:
            return []


    def delta_snr_list(self):
        return [a_i - b_i for a_i, b_i in zip(self.snr_prev_list(), self.snr_list())]


    def snr_components(self, s=None, l=None, method=None) -> list[float]:
        caller = inspect.stack()[1].function
        if s == None: s = self.scale
        if l == None: l = self.zpos
        if method == None:
            method = self.method(l=l)
        if l == 0:
            return []
        try:
            # return self._data['data']['scales'][s]['stack'][l]['alignment_history'][method][-1]['snr']
            components = self._data['data']['scales'][s]['stack'][l]['alignment_history'][method]['snr']
            if type(components) == list:
                return components
            else:
                return [components]
            # return self.method_results(s=s, l=l)['snr']
        except:
            # print_exception()
            logger.warning(f'No SNR components for section {l}, method {method} [caller: {caller}]...\n')
            # return self._data['data']['scales'][s]['stack'][l]['alignment']['method_results']['snr']
            return []
        # if self.method(s=s, l=l) == 'Manual-Hint':
        #     files = self.get_signals_filenames()
        #     n = len(files)
        #     if ('snr' in mr) and (n == len(mr['snr'])):
        #         return mr['snr']
        #     else:
        #         return [0.0]*n
        # else:
        #     try:
        #         return mr['snr']
        #     except:
        #         print_exception()
        #         logger.warning('No SNR data for %s, layer %d' %(s,l))
        #         return []


    def snr_prev_components(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return self._data['data']['scales'][s]['stack'][l][
                'alignment']['previous_method_results']['snr_prev']
        except:
            logger.warning('No Previous SNR data for %s, layer %d' %(s,l))
            return []


    def snr_report(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            # return self._data['data']['scales'][s]['stack'][l]['alignment']['method_results']['snr_report']
            return self._data['data']['scales'][s]['stack'][l]['alignment_history'][self.get_current_method(s=s, l=l)]['snr_report']
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
            if not 'snr' in l['alignment']['method_results']:
                unavailable.append((i, self.name_base(s=s, l=i)))
        return unavailable


    def snr_max_all_scales(self) -> float:
        #Todo refactor, store local copy, this is a bottleneck
        max_snr = []
        # logger.critical(f'self.scalesAlignedAndGenerated: {self.scalesAlignedAndGenerated}')
        try:
            for s in self.scales():
                if self.is_aligned(s=s):
                    # m = max(self.snr_list(s=s))
                    m = max(self.snr_list(s=s)[1:]) #0601+ temp fix for self-alignment high SNR bug on first image
                    # logger.critical(f'm: {m}')
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


    def snr_prev_average(self, scale=None) -> float:
        # logger.info('caller: %s...' % inspect.stack()[1].function)
        if scale == None: scale = self.scale
        # NOTE: skip the first layer which does not have an SNR value s may be equal to zero
        try:
            return statistics.fmean(self.snr_prev_list(s=scale)[1:])
        except:
            logger.warning('No previous SNR data found - returning 0.0...')
            return 0.0

    def method(self, s=None, l=None):
        '''Gets the alignment method
        Returns:
            str: the alignment method for a single section
        '''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # return self._data['data']['scales'][s]['stack'][l]['alignment']['method']
        return self._data['data']['scales'][s]['stack'][l]['current_method']

    def method_pretty(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        convert = {'grid-default': 'Grid Default', 'grid-custom': 'Grid Custom',
                   'manual-strict': 'Manual Strict', 'manual-hint': 'Manual Hint'}
        return convert[self._data['data']['scales'][s]['stack'][l]['current_method']]


    def set_all_methods_automatic(self):
        '''Sets the alignment method of all sections and all scales to Auto-SWIM.'''
        # for s in self.scales():
        for l in range(len(self)):
            self._data['data']['scales'][self.scale]['stack'][l]['current_method'] = 'grid-default'

        self.set_manual_swim_windows_to_default()

    def manpoints(self, s=None, l=None):
        '''Returns manual correspondence points in Neuroglancer format'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints']

    def set_manpoints(self, role, matchpoints, l=None):
        '''Sets manual correspondence points for a single section at the current scale_key, and applies
         scaling factor then sets the same points for all scale_key levels above the current scale_key.'''
        if l == None: l = self.zpos
        logger.info(f"Writing manual points to project dictionary for section #{l}: {matchpoints}")
        # scale_vals  = [x for x in self.scale_vals() if x <= self.scale_val()]
        # scales      = [get_scale_key(x) for x in scale_vals]
        glob_coords = []
        fac = self.scale_val()
        for p in matchpoints:
            glob_coords.append((p[0] * fac, p[1] * fac))

        # for s in self.scales():
        for s in self.finer_scales():
            # set manual points in Neuroglancer coordinate system
            fac = get_scale_val(s)
            coords = []
            for p in glob_coords:
                coords.append((p[0] / fac, p[1] / fac))
            logger.info(f'Setting manual points for {s}: {coords}')
            self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints'][role] = coords

            # set manual points in MIR coordinate system
            img_width = self.image_size(s=s)[0]
            mir_coords = [[img_width - pt[1], pt[0]] for pt in coords]
            self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints_mir'][role] = mir_coords

            # if role == 'base':
            #     if l+1 in range(0,len(self)):
            #         self._data['data']['scales'][s]['stack'][l+1]['alignment']['manpoints']['ref'] = coords
            #         self._data['data']['scales'][s]['stack'][l+1]['alignment']['manpoints_mir']['ref'] = mir_coords


    def manpoints_mir(self, role, s=None, l=None):
        '''Returns manual correspondence points in MIR format'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints_mir'][role]

    def manpoints_pretty(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        ref = self.manpoints()['ref']
        base = self.manpoints()['base']
        return (['(%d, %d)' % (round(x1), round(y1)) for x1, y1 in ref],
                ['(%d, %d)' % (round(x1), round(y1)) for x1, y1 in base])

    def manpoints_rounded(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        ref = self.manpoints()['ref']
        base = self.manpoints()['base']
        return zip([(round(x1), round(y1)) for x1, y1 in ref],
                [(round(x1), round(y1)) for x1, y1 in base])


    def find_layers_with_manpoints(self, s=None) -> list:
        '''Returns the list of layers that have match points'''
        if s == None: s = self.scale
        indexes, names = [], []
        try:
            for i,layer in enumerate(self.stack()):
                r = layer['alignment']['manpoints']['ref']
                b = layer['alignment']['manpoints']['base']
                if (r != []) or (b != []):
                    indexes.append(i)
                    names.append(os.path.basename(layer['filename']))
            return list(zip(indexes, names))
        except:
            print_exception()
            logger.warning('Unable to To Return List of Match Point Layers')
            return []

    def print_all_manpoints(self):
        logger.info('Match Points:')
        for i, sec in enumerate(self.stack()):
            r = sec['alignment']['manpoints']['ref']
            b = sec['alignment']['manpoints']['base']
            if r != []:
                logger.info(f'Index: {i}, Ref, Match Points: {str(r)}')
            if b != []:
                logger.info(f'Index: {i}, Base, Match Points: {str(b)}')


    def getmpFlat(self, s=None, l=None):
        # logger.critical('')
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            mps = self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints']
            # ref = [(0.5, x[0], x[1]) for x in mps['ref']]
            # base = [(0.5, x[0], x[1]) for x in mps['base']]
            ref = [(l, x[0], x[1]) for x in mps['ref']]
            base = [(l, x[0], x[1]) for x in mps['base']]
            return {'ref': ref, 'base': base}
        except:
            print_exception()
            return {'ref': [], 'base': []}

    def clearMps(self, l=None):
        if l == None: l = self.zpos
        # scale_vals = [x for x in self.scale_vals() if x >= self.scale_val()]
        # scales = [get_scale_key(x) for x in scale_vals]
        # for s in self.scales():
        for s in self.finer_scales():
            self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints']['ref'] = []
            self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints']['base'] = []
            self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints_mir']['ref'] = []
            self._data['data']['scales'][s]['stack'][l]['alignment']['manpoints_mir']['base'] = []


    # def clearAllMps(self):
    #     for layer in self.stack():
    #         layer['alignment']['manpoints']['ref'] = []
    #         layer['alignment']['manpoints']['base'] = []

    # def annotations(self, s=None, l=None):
    #     if s == None: s = self.scale_key
    #     if l == None: l = self.zpos
    #     layer = self._data['data']['scales'][s]['stack'][l]
    #     r = layer['images']['ref']['metadata']['annotations']
    #     b = layer['images']['base']['metadata']['annotations']
    #     a = layer['images']['aligned']['metadata']['annotations']
    #     combined = {'ref': r, 'base': b, 'aligned': a}
    #     logger.info(f'Ref, Annotations: {str(r)}')
    #     logger.info(f'Base, Annotations: {str(b)}')
    #     logger.info(f'Base, Annotations: {str(a)}')
    #     return combined


    def afm(self, s=None, l=None) -> list:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            # return self._data['data']['scales'][s]['stack'][l]['alignment']['method_results']['affine_matrix']
            return self._data['data']['scales'][s]['stack'][l]['alignment_history'][self.get_current_method(s=s,l=l)]['affine_matrix']
        except:
            print_exception()
            return [[[1, 0, 0], [0, 1, 0]]]


    def cafm_hashable(self, s=None, end=None):
        if s == None: s = self.scale
        if end == None: end = self.zpos
        # return [tuple(map(tuple, x)) for x in self.cafm_list(s=s,end=end)]
        # return hash(str(self.cafm_list(s=s,end=end)))
        try:
            return hash(str(self.cafm(s=s, l=end)))
        except:
            caller = inspect.stack()[1].function
            print_exception(extra=f'end={end}, caller: {caller}')

    def cafm(self, s=None, l=None) -> list:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return self._data['data']['scales'][s]['stack'][l]['alignment']['method_results']['cumulative_afm']
            # return self._data['data']['scales'][s]['stack'][l]['alignment_history'][self.get_current_method(s=s, l=l)]['cumulative_afm']
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

    def cafm_registered_hash(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # return self._data['data']['scales'][s]['stack'][l]['alignment_history'][self.get_current_method(l=l)]['cafm_hash']
        return self._data['data']['scales'][s]['stack'][l]['cafm_alignment_hash']


    def cafm_current_hash(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # return hash(str(self.cafm_list(s=s, end=l)))
        return self.cafm_hashable(s=s, end=l)

    def register_cafm_hashes(self, start, end, s=None):
        logger.info('Registering cafm hashes...')
        if s == None: s = self.scale
        # for i, layer in enumerate(self.get_iter(s)):
        for i in range(start, end):
            # self._data['data']['scales'][s]['stack'][i]['alignment_history'][self.get_current_method(l=i)]['cafm_hash'] = \
            #     self.cafm_current_hash(l=i)
            self._data['data']['scales'][s]['stack'][i]['cafm_alignment_hash'] = self.cafm_current_hash(l=i)


    def cafm_hash_comports(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self.cafm_registered_hash(s=s, l=l) == self.cafm_current_hash(s=s, l=l)


    def bias_data_path(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.join(self.dest(), s, 'bias_data')

    def show_afm(self):
        logger.info('\nafm = %s\n' % ' '.join(map(str, self.afm())))

    def show_cafm(self):
        logger.info('\ncafm = %s\n' % ' '.join(map(str, self.cafm())))

    def resolution(self, s=None):
        if s == None: s = self.scale
        # logger.info('returning: %s' % str(self._data['data']['scales'][s]['resolution']))
        return self._data['data']['scales'][s]['resolution']
    #
    # def res_x(self, s=None) -> int:
    #     if s == None: s = self.scale_key
    #     if 'resolution_x' in self._data['data']['scales'][s]:
    #         return int(self._data['data']['scales'][s]['resolution_x'])
    #     else:
    #         logger.warning('resolution_x not in dictionary')
    #         # return int(2)
    #
    # def res_y(self, s=None) -> int:
    #     if s == None: s = self.scale_key
    #     if 'resolution_y' in self._data['data']['scales'][s]:
    #         return int(self._data['data']['scales'][s]['resolution_y'])
    #     else:
    #         logger.warning('resolution_y not in dictionary')
    #         # return int(2)
    #
    # def res_z(self, s=None) -> int:
    #     if s == None: s = self.scale_key
    #     if 'resolution_z' in self._data['data']['scales'][s]:
    #         return int(self._data['data']['scales'][s]['resolution_z'])
    #     else:
    #         logger.warning('resolution_z not in dictionary')
    #         # return int(50)

    # def set_resolutions(self, scale_key, res_x:int, res_y:int, res_z:int):
    #     self._data['data']['scales'][scale_key]['resolution_x'] = res_x
    #     self._data['data']['scales'][scale_key]['resolution_y'] = res_y
    #     self._data['data']['scales'][scale_key]['resolution_z'] = res_z

    def set_resolution(self, s, res_x:int, res_y:int, res_z:int):
        self._data['data']['scales'][s]['resolution'] = (res_z, res_y, res_x)


    def get_user_zarr_settings(self):
        '''Returns user settings for cname, clevel, chunkshape as tuple (in that order).'''
        return (self.cname, self.clevel, self.chunkshape)

    def scale_pretty(self, s=None) -> str:
        if s == None: s = self.scale
        return 'Scale %d' % self.scale_val(s=s)

    def scale_val(self, s=None) -> int:
        if s == None: s = self.scale
        while s.startswith('scale_'):
            s = s[len('scale_'):]
        return int(s)

    def scale_vals(self) -> list[int]:
        return [int(v) for v in sorted([get_scale_val(s) for s in self.scales()])]

    def n_scales(self) -> int:
        '''Returns the number of scales in s pyramid'''
        try:
            n_scales = len(self._data['data']['scales'].keys())
            return n_scales
        except:
            logger.warning('No Scales Found - Returning 0')

    def scales(self) -> list[str]:
        '''Get scales list.
        Faster than O(n*m) performance.
        Preserves order of scales.'''
        return natural_sort([key for key in self._data['data']['scales'].keys()])

    def downscales(self) -> list[str]:
        '''Get downscales list (similar to scales() but with scale_1 removed).
        Faster than O(n*m) performance.
        Preserves order of scales.'''
        lst = natural_sort([key for key in self._data['data']['scales'].keys()])
        try:
            lst.remove('scale_1')
        except:
            print_exception()
        return lst

    def skipped(self, s=None, l=None) -> bool:
        '''Called by get_axis_data'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return bool(self._data['data']['scales'][s]['stack'][l]['skipped'])
        except IndexError:
            logger.warning(f'Index {l} is out of range.')
        except:
            print_exception()
            logger.warning('Returning False, but there was a problem')
            return False

    def skips_list(self, s=None) -> list:
        '''Returns the list of skipped images for a s'''
        if s == None: s = self.scale
        indexes, names = [], []
        try:
            for i,layer in enumerate(self.stack(s=s)):
                if layer['skipped'] == True:
                    indexes.append(i)
                    names.append(os.path.basename(layer['filename']))
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
                if self._data['data']['scales'][s]['stack'][i]['skipped'] == True:
                    f = os.path.basename(self._data['data']['scales'][s]['stack'][i]['filename'])
                    lst.append(f)
            return lst
        except:
            logger.warning('Unable to To Return Skips By Name List')
            return []


    def swim_iterations(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['alignment']['swim_settings']['iterations']

    def set_swim_iterations(self, val, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        self._data['data']['scales'][s]['stack'][l]['alignment']['swim_settings']['iterations'] = val


    def swim_settings(self, s=None, l=None):
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['alignment']['swim_settings']


    def set_swim_iterations_glob(self, val:int, ):
        # for s in self.scales():
        for s in self.finer_scales():
            for i in range(len(self)):
                self._data['data']['scales'][s]['stack'][i]['alignment']['swim_settings']['iterations'] = val

    def whitening(self) -> float:
        '''Returns the Signal Whitening Factor for the Current Layer.'''
        return float(self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['swim_settings']['signal-whitening'])


    def set_whitening(self, f: float) -> None:
        '''Sets the Whitening Factor for the Current Layer.'''
        # self._data['data']['scales'][self.scale_key]['stack'][self.zpos]['alignment']['method_data']['whitening_factor'] = f
        self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['swim_settings']['signal-whitening'] = f


    def swim_window(self) -> float:
        '''Returns the SWIM Window for the Current Layer.'''
        return float(self.stack()[self.zpos]['alignment']['swim_settings']['win_scale_factor'])

    def swim_1x1_custom_px(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        # return self.stack()[self.zpos]['alignment']['swim_settings']['grid-custom-px']
        return tuple(self._data['data']['scales'][s]['stack'][l]['alignment']['grid_custom_px_1x1'])

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
        self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['grid_custom_px_1x1'] = [pixels, pixels_y]
        if (self.swim_2x2_custom_px()[0] * 2) > pixels:
            self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['grid_custom_px_2x2'] = \
                [int(pixels / 2  + 0.5), int(pixels_y / 2 + 0.5)]



    def propagate_swim_1x1_custom_px(self, start, end):
        '''Sets the SWIM Window for the Current Section across all scales.'''
        # img_w, img_h = self.image_size(s=self.scale_key)
        for l in range(start, end):
            pixels = self._data['data']['scales'][self.scale]['stack'][l]['alignment']['grid_custom_px_1x1']
            for s in self.finer_scales():
                sf = self.scale_val() / get_scale_val(s)
                self._data['data']['scales'][s]['stack'][l]['alignment'][
                    'grid_custom_px_1x1'] = [int(pixels[0] * sf + 0.5), int(pixels[1] * sf + 0.5)]


    def swim_2x2_custom_px(self, s=None, l=None):
        '''Returns the SWIM Window in pixels'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return tuple(self._data['data']['scales'][s]['stack'][l]['alignment']['grid_custom_px_2x2'])

    def set_swim_2x2_custom_px(self, pixels=None):
        '''Returns the SWIM Window in pixels'''
        caller = inspect.stack()[1].function
        # if pixels == None:
        #     self.set_auto_swim_windows_to_default(current_only=True)
        if (pixels % 2) == 1:
            pixels -= 1


        img_w, img_h = self.image_size(s=self.scale)
        pixels_y = (pixels / img_w) * img_h
        # for s in self.scales():

        logger.critical(f'[{caller}] pixels: {pixels}, pixels_y: {pixels_y}')
        logger.critical(f"    {int(self.swim_1x1_custom_px()[1] / 2 + 0.5)}")

        if (2 * pixels) <= self.swim_1x1_custom_px()[0]:
            self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['grid_custom_px_2x2'] = [pixels, pixels_y]
        else:
            force_pixels = [int(self.swim_1x1_custom_px()[0] / 2 + 0.5),int(self.swim_1x1_custom_px()[1] / 2 + 0.5)]
            if (force_pixels[0] % 2) == 1:
                force_pixels[0] -= 1
                force_pixels[1] -= 1
            self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['grid_custom_px_2x2'] = force_pixels


    def propagate_swim_2x2_custom_px(self, start, end):
        '''Returns the SWIM Window in pixels'''
        # img_w, img_h = self.image_size(s=self.scale_key)
        for l in range(start, end):
            pixels = self._data['data']['scales'][self.scale]['stack'][l]['alignment']['grid_custom_px_2x2']
            for s in self.finer_scales(include_self=False):
                sf = self.scale_val() / get_scale_val(s)  # scale_key factor
                self._data['data']['scales'][s]['stack'][l]['alignment']['grid_custom_px_2x2'] = [int(pixels[0] * sf + 0.5), int(pixels[1] * sf + 0.5)]



    #Todo 0612
    def set_auto_swim_windows_to_default(self, s_list=None, factor=None, current_only=False) -> None:
        logger.info('')
        import src.config as cfg

        if s_list == None:
            s_list = self.finer_scales()

        img_size = self.image_size(self.scales()[0])  # largest scale_key size
        # man_ww_full = min(img_size[0], img_size[1]) * cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC
        if factor == None:
            factor = cfg.DEFAULT_AUTO_SWIM_WINDOW_PERC
        man_ww_full = img_size[0] * factor, img_size[1] * factor
        # for s in self.scales():
        for s in s_list:
            man_ww_x = int(man_ww_full[0] / self.scale_val(s) + 0.5)
            man_ww_y = int(man_ww_full[1] / self.scale_val(s) + 0.5)

            # self._data['data']['defaults'].setdefault(s, {})
            # self._data['data']['defaults'][s]['swim-window-px'] = [man_ww_x, man_ww_y]
            if current_only:
                self.stack(s)[self.zpos]['alignment']['grid_custom_px_1x1'] = [int(man_ww_x), int(man_ww_y)]
                self.stack(s)[self.zpos]['alignment']['grid_custom_px_2x2'] = [int(man_ww_x / 2 + 0.5), int(man_ww_y / 2 + 0.5)]
            else:
                self._data['data']['defaults'].setdefault(s, {})
                self._data['data']['defaults'][s]['swim-window-px'] = [man_ww_x, man_ww_y]
                for i in range(len(self)):
                    self.stack(s)[i]['alignment']['grid_custom_px_1x1'] = [int(man_ww_x), int(man_ww_y)]
                    self.stack(s)[i]['alignment']['grid_custom_px_2x2'] = [int(man_ww_x / 2 + 0.5), int(man_ww_y / 2 + 0.5)]

    def manual_swim_window_px(self, s=None, l=None) -> int:
        '''Returns the SWIM Window for the Current Layer.'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return int(self._data['data']['scales'][s]['stack'][l]['alignment']['manual_swim_window_px'])

    def set_manual_swim_window_px(self, pixels=None) -> None:
        '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
        logger.critical(f'Setting Local SWIM Window to [{pixels}] pixels...')

        if (pixels % 2) == 1:
            pixels -= 1

        self._data['data']['scales'][self.scale]['stack'][self.zpos]['alignment']['manual_swim_window_px'] = pixels


    def propagate_manual_swim_window_px(self, start, end) -> None:
        '''Sets the SWIM Window for the Current Layer when using Manual Alignment.'''
        # logger.info('Propagating swim regions to finer scales...')
        for l in range(start, end):
            pixels = self._data['data']['scales'][self.scale]['stack'][l]['alignment']['manual_swim_window_px']
            for s in self.finer_scales():
                sf = self.scale_val() / get_scale_val(s)  # scale_key factor
                self._data['data']['scales'][s]['stack'][l]['alignment']['manual_swim_window_px'] = int(pixels * sf + 0.5)

    def set_manual_swim_windows_to_default(self, s_list=None, current_only=False) -> None:
        # logger.info('')
        import src.config as cfg
        if s_list == None:
            s_list = self.finer_scales()

        img_size = self.image_size(self.scales()[0])  # largest scale_key size
        man_ww_full = min(img_size[0], img_size[1]) * cfg.DEFAULT_MANUAL_SWIM_WINDOW_PERC
        # for s in self.scales():
        for s in s_list:
            man_ww = man_ww_full / self.scale_val(s)
            # logger.info(f'Manual SWIM window size for {s} to {man_ww}')
            if current_only:
                self.stack(s)[self.zpos]['alignment']['manual_swim_window_px'] = man_ww
            else:
                for i in range(len(self)):
                    self.stack(s)[i]['alignment']['manual_swim_window_px'] = man_ww


    #
    # def set_manual_swim_windows_to_cur_val(self) -> None:
    #     logger.info('')
    #     ww = self.swim_window()
    #     scale_1_ww = ww * self.scale_val()
    #     # scale_vals  = [x for x in self.scale_vals() if x <= self.scale_val()]
    #     # scales      = [get_scale_key(x) for x in scale_vals]
    #     # for s in self.scales():
    #     for s in self.finer_scales():
    #         self._data['data']['scales'][s]['stack'][self.zpos][
    #             'alignment']['manual_swim_window_px'] = scale_1_ww / get_scale_val(s)


    # def propagate_manual_regions(self, s=None):
    #     if s==None: s=self.scale_key
    #
    #     # scale_1_ww = ww * self.scale_val()
    #     # scale_vals  = [x for x in self.scale_vals() if x <= self.scale_val()]
    #     # scales      = [get_scale_key(x) for x in scale_vals]
    #     # for s in self.scales():
    #
    #
    #     for scale_key in self.finer_scales(s=s):
    #         for section in range(0,len(self)):
    #             ww = self.manual_swim_window_px(s=s)
    #             self._data['data']['scales'][scale_key]['stack'][section][
    #                 'alignment']['manual_settings']['manual_swim_window_px'] = ww * (1 / get_scale_val(s))



    def bounding_rect(self, s=None):
        if s == None: s = self.scale
        try:
            return self._data['data']['scales'][s]['bounding_rect']
        except:
            try:
                self.set_bounding_rect(ComputeBoundingRect(self.stack(s=s), scale=s))
                return self._data['data']['scales'][s]['bounding_rect']
            except:
                logger.warning('Unable to return a bounding rect (s=%s)' % s)
                return None

    def image_size(self, s=None) -> tuple:
        if s == None: s = self.scale
        caller = inspect.stack()[1].function
        # logger.info('Called by %s, s=%s' % (inspect.stack()[1].function, s))
        try:
            return tuple(self._data['data']['scales'][s]['image_src_size'])
        except:
            logger.info(f"[{caller}] No key 'image_src_size' found (scale_key:{s}). Adding it now...")
            try:
                self.set_image_size(s=s)
                answer = tuple(self._data['data']['scales'][s]['image_src_size'])
                logger.info(f'Returning {answer}')
                return answer
            except:
                print_exception()
                logger.warning('Unable to return the image size (s=%s)' % s)

    def set_image_size(self, s=None) -> None:
        if s == None: s = self.scale
        caller = inspect.stack()[1].function
        # logger.info(f"[{caller}] scale_key={s}")
        self._data['data']['scales'][s]['image_src_size'] = list(ImageSize(self.path_base(s=s)))
        # self._data['data']['scales'][s]['image_src_size'] = list(ImageIOSize(self.path_base(s=s)))
        # val = self._data['data']['scales'][s]['image_src_size']
        # logger.critical(f'Just Set {s} image size to {val}')

    def image_size_aligned(self, s=None) -> tuple:
        if s == None: s = self.scale
        logger.info('Called by %s, s=%s' % (inspect.stack()[1].function, s))
        try:
            return tuple(self._data['data']['scales'][s]['image_aligned_size'])
        except:
            logger.info(f"No key 'image_aligned_size' found (scale_key:{s}). Adding it now...")
            try:
                self.set_image_aligned_size(s=s)
                answer = tuple(self._data['data']['scales'][s]['image_aligned_size'])
                logger.info(f'Returning {answer}')
                return answer
            except:
                print_exception()
                logger.warning('Unable to return the image size (s=%s)' % s)

    def set_image_aligned_size(self, s=None) -> None:
        if s == None: s = self.scale
        self._data['data']['scales'][s]['image_aligned_size'] = ImageSize(self.path_aligned(s=s))
        # self._data['data']['scales'][s]['image_aligned_size'] = ImageIOSize(self.path_aligned(s=s))
        val = self._data['data']['scales'][s]['image_src_size']
        # logger.info(f'Just Set {s} image size to {val}')
        # logger.info(f'Aligned Image Size is {self.scale_pretty(s=s)}: {self.image_size(s=s)}')

    def full_scale_size(self):
        try:
            return self.image_size('scale_1')
        except:
            print_exception()
            return (0,0)


    # def poly_order(self, s=None) -> int:
    #     '''Returns the Polynomial Order for the Current Scale.'''
    #     if s == None: s = self.scale_key
    #     return int(self._data['data']['scales'][s]['poly_order'])

    # def use_corrective_polynomial(self) -> bool:
    #     '''Gets the Null Cafm Trends On/Off State for the Current Scale.'''
    #     # return bool(self._data['data']['scales'][s]['null_cafm_trends'])
    #     return bool(self._data['data']['defaults']['use-corrective-polynomial'])

    # def corrective_polynomial(self, s=None) -> int:
    #     '''Gets the Null Cafm Trends On/Off State for the Current Scale.'''
    #     # return bool(self._data['data']['scales'][s]['null_cafm_trends'])
    #     return int(self._data['data']['defaults']['corrective-polynomial'])

    # def al_option(self, s=None) -> str:
    #     '''Gets the Alignment Option for the Current Scale.'''
    #     if s == None: s = self.scale_key
    #     return self._data['data']['scales'][s]['method_data']['alignment_option']

    def path_ref(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return self._data['data']['scales'][s]['stack'][l]['reference']

    def path_base(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            name = self._data['data']['scales'][s]['stack'][l]['filename']
            return name
        except:
            print_exception()

    def name_base(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return os.path.basename(self._data['data']['scales'][s]['stack'][l]['filename'])
        except:
            return ''

    def name_ref(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            return os.path.basename(self._data['data']['scales'][s]['stack'][l]['reference'])
        except:
            return ''

    def path_aligned(self, s=None, l=None) -> str:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        return os.path.join(self.dest(), s, 'img_aligned', self.name_base(l=l))

    def zarr_scale_paths(self):
        l = []
        for s in self.scales():
            # l.append(os.path.join(self._data['data']['destination_path'], s + '.zarr'))
            l.append(os.path.join(self._data['data']['destination_path'], 'img_src.zarr', s + str(get_scale_val(s))))
        return l

    def roles(self):
        l, s = self.zpos, self.scale
        return self._data['data']['scales'][s]['stack'][l]['images'].keys()

    def set_destination(self, s):
        self._data['data']['destination_path'] = s

    def set_previous_results(self, s=None):
        # logger.info('Setting PREVIOUS SNR, caller: %s...' % inspect.stack()[1].function)
        if s == None: s = self.scale
        logger.info('')
        try:
            for l in range(len(self)):
                self._data['data']['scales'][s]['stack'][l][
                    'alignment']['previous_method_results'] = \
                    self._data['data']['scales'][s]['stack'][l][
                        'alignment']['method_results']
        except:
            print_exception()
            logger.warning('Unable to set previous SNR...')

    def set_skip(self, b: bool, s=None, l=None) -> None:
        if s == None: s = self.scale
        if l == None: l = self.zpos
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['data']['scales'][s]['stack'][l]['skipped'] = b


    def has_bb(self, s=None) -> bool:
        '''Returns the Has Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.scale
        return bool(self._data['data']['scales'][s]['has_bounding_rect'])


    def set_has_bb(self, b:bool, s=None):
        '''Returns the Has Bounding Rectangle On/Off State for the Current Scale.'''
        # logger.info(f'Setting HAS bb to {b}')
        if s == None: s = self.scale
        self._data['data']['scales'][s]['has_bounding_rect'] = b


    def use_bb(self, s=None) -> bool:
        '''Returns the Use Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.scale
        # return bool(self._data['data']['scales'][s]['use_bounding_rect'])
        return bool(self._data['data']['defaults']['bounding-box'])

    def set_use_bounding_rect(self, b: bool) -> None:
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['data']['defaults']['bounding-box'] = bool(b)

    def set_bounding_rect(self, bounding_rect: list, s=None) -> None:
        if s == None: s = self.scale
        self._data['data']['scales'][s]['bounding_rect'] = bounding_rect

    def set_calculate_bounding_rect(self, s=None):
        if s == None: s = self.scale
        self.set_bounding_rect(ComputeBoundingRect(self.stack(s=s)))
        return self.bounding_rect()



    def set_image_size_directly(self, size, s=None):
        if s == None: s = self.scale
        logger.info(f"Setting Image Sizes Directly, {s}, image size: {size}")
        self._data['data']['scales'][s]['image_src_size'] = size

    # def set_poly_order(self, x: int, s=None) -> None:
    #     '''Sets the Polynomial Order for the Current Scale.'''
    #     if s == None: s = self.scale_key
    #     self._data['data']['scales'][s]['poly_order'] = int(x)

    # def set_use_poly_order(self, b: bool) -> None:
    #     '''Sets the Null Cafm Trends On/Off State for the Current Scale.'''
    #     self._data['data']['scales'][self.scale_key]['null_cafm_trends'] = bool(b)

    def set_al_dict(self, aldict, s=None):
        if s == None: s = self.scale
        try:
            self._data['data']['scales'][s]['stack'] = aldict
        except:
            logger.warning('Unable to set alignment dict')

    def set_afm(self, afm: list, s=None, l=None) -> None:
        '''Sets afm as list of lists of floats'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            self._data['data']['scales'][s]['stack'][l][
                'alignment']['method_results']['cumulative_afm'] = afm
        except:
            print_exception()

    def set_cafm(self, cafm: list, s=None, l=None) -> None:
        '''Sets cafm as list of lists of floats'''
        if s == None: s = self.scale
        if l == None: l = self.zpos
        try:
            self._data['data']['scales'][s]['stack'][l]['alignment']['method_results']['cumulative_afm'] = cafm
        except:
            print_exception()


    # def method(self, s=None, l=None):
    #     if s == None: s = self.scale_key
    #     if l == None: l = self.zpos
    #     return self._data['data']['scales'][s]['stack'][l]['alignment']['method']


    def set_destination_absolute(self, head):
        head = os.path.split(head)[0]
        self.set_destination(os.path.join(head, self.dest()))

    def set_paths_absolute(self, filename):
        logger.info(f'Setting Absolute File Paths...')
        # returns path to project file minus extension (should be the project directory)
        self.set_destination(os.path.splitext(filename)[0])
        logger.debug(f'Setting absolute project dest/head: {self.dest()}...')
        try:
            head = self.dest()
            for s in self.scales():
                if s == 'scale_1':
                    pass
                else:
                    for l in self._data['data']['scales'][s]['stack']:
                        # for r in l['images'].keys():
                        # if (not l==0) and (not r=='ref'):
                        # tail = l['images'][r]['filename']
                        tail = l['filename']
                        # l['images'][r]['filename'] = os.path.join(head, tail)
                        l['filename'] = os.path.join(head, tail)
                    # self._data['data']['scales'][s]['stack'][0]['images']['ref']['filename'] = None
        except:
            logger.warning('Setting Absolute Paths Triggered This Exception')
            print_exception()


    def stack(self, s=None) -> dict:
        if s == None: s = self.scale
        return self._data['data']['scales'][s]['stack']


    def aligned_list(self) -> list[str]:
        '''Deprecate this

        Get aligned scales list. Check project datamodel and aligned Zarr group presence.'''
        lst = []
        for s in self.scales():
            r = self._data['data']['scales'][s]['stack'][-1]['alignment']['method_results']
            if r != {}:
                lst.append(s)
        for s in lst:
            if not exist_aligned_zarr(s):
                lst.remove(s)
        return lst

    def not_aligned_list(self):
        return set(self.scales()) - set(get_scales_with_generated_alignments(self.scales()))

    def coarsest_scale_key(self) -> str:
        '''Return the coarsest s key. '''
        return natural_sort([key for key in self._data['data']['scales'].keys()])[-1]

    def next_coarsest_scale_key(self) -> str:
        if self.n_scales() == 1:
            return self.scale
        scales_dict = self._data['data']['scales']
        cur_scale_key = self.scale
        coarsest_scale = list(scales_dict.keys())[-1]
        if cur_scale_key == coarsest_scale:
            return cur_scale_key
        scales_list = []
        for scale_key in scales_dict.keys():
            scales_list.append(scale_key)
        cur_scale_index = scales_list.index(cur_scale_key)
        next_coarsest_scale_key = scales_list[cur_scale_index + 1]
        return next_coarsest_scale_key


    def finer_scales(self, s=None, include_self=True):
        if s == None: s = self.scale
        if include_self:
            return [get_scale_key(x) for x in self.scale_vals() if x <= self.scale_val(s=s)]
        else:
            return [get_scale_key(x) for x in self.scale_vals() if x < self.scale_val(s=s)]


    def clear_all_skips(self):
        try:
            # for scale_key in self.scales():
            for scale in self.finer_scales():
                scale_key = str(scale)
                for layer in self._data['data']['scales'][scale_key]['stack']:
                    layer['skipped'] = False
        except:
            print_exception()

    def append_image(self, file):
        scale = self.scale
        # logger.info("Adding Image: %s, role: base, scale_key: %s" % (file, scale_key))
        self._data['data']['scales'][scale]['stack'].append(copy.deepcopy(layer_template))
        self._data['data']['scales'][scale]['stack'][len(self) - 1]['filename'] = file
        self._data['data']['scales'][scale]['stack'][len(self) - 1]['reference'] = ''

    def append_images(self, files):
        scale = self.scale
        for file in files:
            # logger.info("Adding Image: %s, role: base, scale_key: %s" % (file, scale_key))
            self._data['data']['scales'][scale]['stack'].append(copy.deepcopy(layer_template))
            self._data['data']['scales'][scale]['stack'][len(self) - 1]['filename'] = file
            self._data['data']['scales'][scale]['stack'][len(self) - 1]['reference'] = ''

    # def append_empty(self):
    #     logger.critical('MainWindow.append_empty:')
    #     scale_key = self.scale_key
    #     used_for_this_role = ['base' in l['images'].keys() for l in self.stack(s=scale_key)]
    #     layer_index = -1
    #     if False in used_for_this_role:
    #         layer_index = used_for_this_role.index(False)
    #     else:
    #         self._data['data']['scales'][scale_key]['stack'].append(copy.deepcopy(layer_template))
    #         layer_index_for_new_role = len(self['data']['scales'][scale_key]['stack']) - 1
    #     self._data['data']['scales'][scale_key]['stack'][layer_index]['filename'] = ''


    # def add_img(self, scale_key, layer, role, filename=''):
    #     logger.info(f'Adding Image ({scale_key}, {layer}, {role}): {filename}...')
    #     self._data['data']['scales'][scale_key]['stack'][layer]['images'][role] = copy.deepcopy(image_template)
    #     self._data['data']['scales'][scale_key]['stack'][layer]['images'][role]['filename'] = filename
    #     self._data['data']['scales'][scale_key]['stack'][layer]['img'] = copy.deepcopy(image_template) # 0119+
    #     self._data['data']['scales'][scale_key]['stack'][layer]['img'] = filename                      # 0119+


    def anySkips(self) -> bool:
        if len(self.skips_list()) > 0:
            return True
        else:
            return False

    def set_method_options(self):
        coarsest = self.coarsest_scale_key()
        for s in self.scales():
            if s == coarsest:
                self._data['data']['scales'][s]['isRefinement'] = False
                # self._data['data']['scales'][s]['method_data']['alignment_option'] = 'init_affine'
            else:
                self._data['data']['scales'][s]['isRefinement'] = True
                # self._data['data']['scales'][s]['method_data']['alignment_option'] = 'refine_affine'

            # for i in range(self.n_scales()):
            #     layer = self._data['data']['scales'][s]['stack'][i]
            #     if s == coarsest:
            #         layer['alignment']['method_data']['alignment_option'] = 'init_affine'
            #     else:
            #         layer['alignment']['method_data']['alignment_option'] = 'refine_affine'



    def set_scales_from_string(self, scale_string: str):
        '''This is not pretty. Needs to be refactored ASAP.
        Two callers: 'new_project', 'prepare_generate_scales_worker'
        '''
        # logger.info('')
        cur_scales = list(map(str, self.scale_vals()))
        try:
            input_scales = [str(v) for v in sorted([get_scale_val(s) for s in scale_string.strip().split(' ')])]
        except:
            logger.error(f'Bad input: {scale_string}. Scales Unchanged.')
            input_scales = []

        if (input_scales != cur_scales):
            input_scale_keys = [get_scale_key(v) for v in input_scales]
            scales_to_remove = list(set(self.scales()) - set(input_scale_keys) - {'scale_1'})
            # logger.info(f'Removing Scale Keys: {scales_to_remove}...')
            for key in scales_to_remove:
                self._data['data']['scales'].pop(key)
            scales_to_add = list(set(input_scale_keys) - set(self.scales()))
            # logger.info(f'Adding Scale Keys (copying from scale_1): {scales_to_add}...')
            for key in scales_to_add:
                new_stack = [deepcopy(l) for l in self.stack(s='scale_1')]
                # self._data['data']['scales'][key] = \
                #     {'stack': new_stack, 'method_data': { 'alignment_option': 'init_affine' } }
                self._data['data']['scales'][key] = {'stack': new_stack}


    def first_unskipped(self, s=None):
        if s == None: s = self.scale
        for i,section in enumerate(self.get_iter(s=s)):
            if not section['skipped']:
                return i


    def link_reference_sections(self, s_list=None):
        '''Called by the functions '_callbk_skipChanged' and 'import_multiple_images'
        Link layers, taking into accounts skipped layers'''
        # self.set_default_data()  # 0712 #0802 #original
        # for s in self.scales():
        logger.info('')
        if s_list == None:
            s_list = self.finer_scales()

        for s in s_list:
            skip_list = self.skips_indices(s=s)
            first_unskipped = self.first_unskipped(s=s)
            for layer_index in range(len(self)):
                base_layer = self._data['data']['scales'][s]['stack'][layer_index]
                if layer_index in skip_list:
                    self._data['data']['scales'][s]['stack'][layer_index]['reference'] = ''
                # elif layer_index <= first_unskipped:
                #     self._data['data']['scales'][s]['stack'][layer_index]['reference'] = self._data['data']['scales'][s]['stack'][layer_index]['filename']
                else:
                    j = layer_index - 1  # Find nearest previous non-skipped l
                    while (j in skip_list) and (j >= 0):
                        j -= 1
                    if (j not in skip_list) and (j >= 0):
                        ref = self._data['data']['scales'][s]['stack'][j]['filename']
                        ref = os.path.join(self.dest(), s, 'img_src', ref)
                        # base_layer['images']['ref']['filename'] = ref
                        base_layer['reference'] = ref
            # kludge - set reference of first_unskipped to itself
            self._data['data']['scales'][s]['stack'][first_unskipped]['reference'] = self._data['data']['scales'][s]['stack'][first_unskipped]['filename']


    # def init_link_reference_sections(self):
    #     '''Called by the functions '_callbk_skipChanged' and 'import_multiple_images'
    #     Link layers, taking into accounts skipped layers'''
    #     # self.set_default_data()  # 0712 #0802 #original
    #     # for s in self.scales():
    #     for s in self.finer_scales():
    #         skip_list = self.skips_indices(s=s)
    #         first_unskipped = self.first_unskipped()
    #         logger.info(f'first_unskipped: {first_unskipped}')
    #         for layer_index in range(len(self)):
    #             base_layer = self._data['data']['scales'][s]['stack'][layer_index]
    #             if layer_index in skip_list:
    #                 self._data['data']['scales'][s]['stack'][layer_index]['reference'] = ''
    #             # elif layer_index <= first_unskipped:
    #             #     self._data['data']['scales'][s]['stack'][layer_index]['reference'] = self._data['data']['scales'][s]['stack'][layer_index]['filename']
    #             else:
    #                 j = layer_index - 1  # Find nearest previous non-skipped l
    #                 while (j in skip_list) and (j >= 0):
    #                     j -= 1
    #                 if (j not in skip_list) and (j >= 0):
    #                     ref = self._data['data']['scales'][s]['stack'][j]['filename']
    #                     ref = os.path.join(self.dest(), s, 'img_src', ref)
    #                     # base_layer['images']['ref']['filename'] = ref
    #                     base_layer['reference'] = ref
    #         self._data['data']['scales'][s]['stack'][first_unskipped]['reference'] = self._data['data']['scales'][s]['stack'][first_unskipped]['filename']


    # def propagate_up_from(self, scale_from=None):
    #     if scale_from == None: scale_from=self.scale_key
    #
    #         it = self.get_iter(s=scale_from)
    #
    #
    #         for i, section in enumerate(it):
    #
    #             method = section['current_method']
    #             for s in self.finer_scales(include_self=False):
    #                 self._data['data']['scales'][s]['stack'][i]['current_method']
    #
    #
    #
    #             pass








    def upgrade_data_model(self):
        # Upgrade the "Data Model"
        if self._data['version'] != self._current_version:
            logger.critical('Upgrading Data Model...')

            # Begin the upgrade process:

            if self._data['version'] <= 0.26:
                logger.info("Upgrading datamodel previewmodel from " + str(self._data['version']) + " to " + str(0.27))
                # Need to modify the datamodel previewmodel from 0.26 or lower up to 0.27
                # The "alignment_option" had been in the method_data at each l
                # This new version defines it only at the s level
                # So loop through each s and move the alignment_option from the l to the s
                for scale_key in self.scales():
                    scale = self._data['data']['scales'][scale_key]
                    stack = scale['stack']
                    current_alignment_options = []
                    for layer in stack:
                        if "alignment" in layer:
                            align_method = layer['alignment']
                            if 'method_data' in align_method:
                                if 'alignment_option' in align_method['method_data']:
                                    current_alignment_options.append(align_method['method_data']['alignment_option'])
                    # The current_alignment_options list now holds all of the options for this s (if any)
                    # Start by setting the default for the s option to "init_affine" if none are found
                    scale_option = "init_affine"
                    # If any options were found in this s, search through them for most common
                    if len(current_alignment_options) > 0:
                        # They should all be the same at this s, so set to the first
                        scale_option = current_alignment_options[0]
                        # But check if any are different and then find the most common
                        if current_alignment_options.count(current_alignment_options[0]) != len(
                                current_alignment_options):
                            # There are some that are different, so find the most common option
                            scale_option = max(set(current_alignment_options), key=current_alignment_options.count)
                    # At this point "scale_option" should be the one to use
                    if not ('method_data' in scale):
                        # Ensure that there's some method datamodel
                        scale['method_data'] = {}
                    # Finally set the value
                    scale['method_data']["alignment_option"] = scale_option
                # Now the datamodel previewmodel is at 0.27, so give it the appropriate version
                self._data['version'] = 0.27

            if self._data['version'] == 0.27:
                print("\n\nUpgrading datamodel previewmodel from " + str(self._data['version']) + " to " + str(0.28))
                # Need to modify the datamodel previewmodel from 0.27 up to 0.28
                # The "alignment_option" had been left in the method_data at each l
                # This new version removes that option from the l method datamodel
                # So loop through each s and remove the alignment_option from the l
                for scale_key in self.scales():
                    scale = self._data['data']['scales'][scale_key]
                    stack = scale['stack']
                    current_alignment_options = []
                    for layer in stack:
                        if "alignment" in layer:
                            align_method = layer['alignment']
                            if 'method_data' in align_method:
                                if 'alignment_option' in align_method['method_data']:
                                    align_method['method_data'].pop('alignment_option')
                # Now the datamodel previewmodel is at 0.28, so give it the appropriate version
                self._data['version'] = 0.28

            if self._data['version'] == 0.28:
                print("\n\nUpgrading datamodel previewmodel from " + str(self._data['version']) + " to " + str(0.29))
                # Need to modify the datamodel previewmodel from 0.28 up to 0.29
                # The "use_c_version" was added to the "user_settings" dictionary
                # self._data['user_settings']['use_c_version'] = True #0206-
                # Now the datamodel previewmodel is at 0.29, so give it the appropriate version
                self._data['version'] = 0.29

            if self._data['version'] == 0.29:
                print("\n\nUpgrading datamodel previewmodel from " + str(self._data['version']) + " to " + str(0.30))
                # Need to modify the datamodel previewmodel from 0.29 up to 0.30
                # The "poly_order" was added to the "scales" dictionary
                for scale_key in self.scales():
                    scale = self._data['data']['scales'][scale_key]
                    scale['poly_order'] = 4
                # Now the datamodel previewmodel is at 0.30, so give it the appropriate version
                self._data['version'] = 0.30

            if self._data['version'] == 0.30:
                print("\n\nUpgrading datamodel previewmodel from " + str(self._data['version']) + " to " + str(0.31))
                # Need to modify the datamodel previewmodel from 0.30 up to 0.31
                # The "skipped(1)" annotation is currently unused (now hard-coded in alignem.py)
                # Remove alll "skipped(1)" annotations since they can not otherwise be removed
                for scale_key in self.scales():
                    scale = self._data['data']['scales'][scale_key]
                    stack = scale['stack']
                    for layer in stack:
                        for role in layer['images'].keys():
                            image = layer['images'][role]
                            print("Checking for annotations in image...")
                            if 'metadata' in image.keys():
                                print("Checking for annotations in metadata...")
                                m = image['metadata']
                                if 'annotations' in m.keys():
                                    print("Removing any \"skipped()\" annotations ... ")
                                    m['annotations'] = [a for a in m['annotations'] if not a.startswith('skipped')]
                # Now the datamodel previewmodel is at 0.31, so give it the appropriate version
                self._data['version'] = 0.31
            if self._data['version'] == 0.31:
                print("\n\nUpgrading datamodel previewmodel from " + str(self._data['version']) + " to " + str(0.32))
                # Need to modify the datamodel previewmodel from 0.31 up to 0.32
                #   1) change name of method_results key "affine_matrix" to "afm"
                #   2) change name of method_results key "cumulative_afm" to "cafm"
                #   3) add new method_results key, "aim" and compute/store this value
                #   4) add new method_results key, "c_aim" and compute/store this value
                #   5) add new method_results key, "reconstruct_x_coeff" and compute/store this value
                #   6) add new method_results key, "reconstruct_y_coeff" and compute/store this value
                #   7) add new s key, "bounding_rect_x" and compute/store this value
                #   8) add new s key, "bounding_rect_y" and compute/store this value
                # Note, aim and c_aim are the inverse of afm and cafm
                # Note, cafm and c_aim are the now the cumulative matrices not including
                #       the bounding rect.
                # Note, reconstruct_x_coeff and _y_coeff are the coefficients of the
                #       dim 3 polynomial basis transforms used by RECONSTRUCT.
                #       These coefficients do not include the bounding rect terms.
                #

                # FIXME: leave this commented out until we have finished 1-8 above
                # Now the datamodel previewmodel is at 0.32, so give it the appropriate version
                # data_model ['version'] = 0.32

            # Make the final test
            if self._data['version'] != self._current_version:
                # The datamodel previewmodel could not be upgraded, so return a string with the error
                data_model = 'Version mismatch. Expected "' + str(
                    self._current_version) + '" but found ' + str(
                    self._data['version'])


    def clear_method_results(self, scale=None, start=0, end=None):
        if scale == None: scale = self.scale
        logger.info("Clearing 'method_results'...")
        for layer in self._data['data']['scales'][scale]['stack'][start:end]:
            layer['alignment']['method_results'] = {}


    def make_paths_relative(self, start):
        self.set_destination(os.path.relpath(self.dest(), start=start))
        for s in self.downscales():
            for layer in self.stack(s=s):
                # for role in layer['images'].keys():
                layer['filename'] = os.path.relpath(layer['filename'], start=start)
                layer['reference'] = os.path.relpath(layer['reference'], start=start)


    # Properties are class attributes that manage instance attributes
    # You can think of a property as a collection of methods bundled together
    # loc = property(fget=layer, fset=set_layer, fdel=None, doc='Location In Stack Property')

def get_scale_key(scale_val) -> str:
    '''Create a key like "scale_#" from either an integer or a string'''
    s = str(scale_val)
    while s.startswith('scale_'):
        s = s[len('scale_'):]
    return 'scale_' + s


def get_scale_val(scale_of_any_type) -> int:
    '''Converts s key to integer (i.e. 'scale_1' as string -> 1 as int)
    TODO: move this to glanceem_utils'''
    scale = scale_of_any_type
    try:
        if type(scale) == type(1):
            return scale
        else:
            while scale.startswith('scale_'):
                scale = scale[len('scale_'):]
            return int(scale)
    except:
        logger.warning('Unable to return s value')

def natural_sort(l):
    '''Natural sort a list of strings regardless of zero padding'''
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


if __name__ == '__main__':
    data = DataModel()
    print('Data Model Version: ' + str(data['version']))
    print(data)
