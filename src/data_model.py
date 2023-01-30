#!/usr/bin/env python3

"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""
import os
import copy
import json
import inspect
import logging
import platform
import statistics
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import src.config as cfg
from src.data_structs import data_template, layer_template, image_template
from src.helpers import print_exception, natural_sort, exist_aligned_zarr, get_scale_key, \
    get_scale_val, get_scales_with_generated_alignments
from src.funcs_image import ComputeBoundingRect, ImageSize

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


class DataModel:
    """ Encapsulate datamodel dictionary and wrap with methods for convenience """
    def __init__(self, data=None, name=None, quitely=False, mendenhall=False):
        self._current_version = 0.50
        self.quietly = quitely
        self.scalesAlignedAndGenerated = []
        self.nScalesAlignedAndGenerated = None
        self.nscales = None
        self.nSections = None
        self.curScale = None
        if not self.quietly:
            logger.info(f'Constructing Data Model (caller:{inspect.stack()[1].function})...')

        if data:
            self._data = data
        else:
            self._data = copy.deepcopy(data_template)
            current_time = datetime.now()
            # self._data['created'] = current_time.strftime("%m/%d/%Y, %H:%M:%S")
            self._data['created'] = current_time.strftime("%d-%m-%y %H:%M:%S")
            self.set_system_info()

        # if not self.layer():
        #     self.set_layer(0)

        if not self.quietly:
            self._data['last_opened'] = datetime.now().strftime("%d-%m-%y %H:%M:%S")
            # self.set_defaults()

        if name:
            self._data['data']['destination_path'] = name
        self._data['data']['mendenhall'] = mendenhall

        if not self.quietly:
            self.set_defaults()
        if not self.layer():
            self.set_layer(0)

    def __setitem__(self, key, item):
        self._data[key] = item

    def __getitem__(self, key):
        return self._data[key]

    def __repr__(self):
        return self.to_json()

    def __copy__(self):
        cls = self.__class__
        result = cls.__new__(cls)
        result.__dict__.update(self.__dict__)
        return result

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            setattr(result, k, deepcopy(v, memo))
        return result

    def __len__(self):
        try:
            return self.n_sections()
        except:
            logger.warning('No Images Found')

    def created(self):
        return self._data['created']

    def last_opened(self):
        return self._data['last_opened']

    def is_aligned(self, s=None):
        # logger.info('')
        if s == None: s = self.curScale
        if sum(self.snr_list(s=s)) < 1:
            # logger.info('is_aligned is returning False')
            return False
        else:
            # logger.info('is_aligned is returning True')
            return True

    def is_aligned_and_generated(self, s=None) -> bool:
        if s == None: s = cfg.data.scale()
        if s in self.scalesAlignedAndGenerated:
            return True
        else:
            return False

    def update_cache(self):
        logger.info('Caching data model variables...')
        self.curScale = self.scale()
        try:
            self.scalesAlignedAndGenerated = get_scales_with_generated_alignments(self.scales())
            self.nScalesAlignedAndGenerated = len(self.scalesAlignedAndGenerated)
        except:
            print_exception()
        self.scalesList = self.scales()
        self.nscales = len(self.scalesList)
        self.nSections = self.n_sections()

    def set_t_scaling(self, dt):
        self._data['data']['t_scaling'] = '%.3f' % dt

    def set_t_scaling_convert_zarr(self, dt):
        self._data['data']['t_scaling_convert_zarr'] = '%.3f' % dt

    def set_t_thumbs(self, dt):
        self._data['data']['t_thumbs'] = '%.3f' % dt

    def set_t_align(self, dt, s=None):
        if s == None: s = cfg.data.scale()
        self._data['data']['scales'][s]['t_align'] = '%.3f' % dt

    def set_t_generate(self, dt, s=None):
        if s == None: s = cfg.data.scale()
        self._data['data']['scales'][s]['t_generate'] = '%.3f' % dt

    def set_t_convert_zarr(self, dt, s=None):
        if s == None: s = cfg.data.scale()
        self._data['data']['scales'][s]['t_convert_zarr'] = '%.3f' % dt

    def set_t_thumbs_aligned(self, dt, s=None):
        if s == None: s = cfg.data.scale()
        self._data['data']['scales'][s]['t_thumbs_aligned'] = '%.3f' % dt

    def set_t_thumbs_spot(self, dt, s=None):
        if s == None: s = cfg.data.scale()
        self._data['data']['scales'][s]['t_thumbs_spot'] = '%.3f' % dt

    def set_thumb_scaling_factor_source(self, factor:int):
        self._data['data']['thumb_scaling_factor_source'] = factor

    def set_thumb_scaling_factor_aligned(self, factor:int, s:str):
        self._data['data']['scales'][s]['thumb_scaling_factor_aligned'] = factor

    def set_thumb_scaling_factor_corr_spot(self, factor:int, s:str):
        self._data['data']['scales'][s]['thumb_scaling_factor_corr_spot'] = factor

    def set_defaults(self):
        # logger.info(f'caller: {inspect.stack()[1].function}')
        self._data['user_settings'].setdefault('mp_marker_size', cfg.MP_SIZE)
        self._data['user_settings'].setdefault('mp_marker_lineweight', cfg.MP_LINEWEIGHT)
        self._data['data'].setdefault('cname', cfg.CNAME)
        self._data['data'].setdefault('clevel', cfg.CLEVEL)
        self._data['data'].setdefault('chunkshape', (cfg.CHUNK_Z, cfg.CHUNK_Y, cfg.CHUNK_X))

        # for s in self.scales():
        for s in self._data['data']['scales'].keys():
            logger.info('Setting defaults for %s' % self.scale_pretty(s=s))
            scale = self._data['data']['scales'][s]
            scale.setdefault('use_bounding_rect', cfg.DEFAULT_BOUNDING_BOX)
            scale.setdefault('null_cafm_trends', cfg.DEFAULT_NULL_BIAS)
            scale.setdefault('poly_order', cfg.DEFAULT_POLY_ORDER)
            scale.setdefault('resolution', (cfg.DEFAULT_RESZ, cfg.DEFAULT_RESY, cfg.DEFAULT_RESX))

            for layer_index in range(len(scale['alignment_stack'])):
                layer = scale['alignment_stack'][layer_index]
                layer.setdefault('align_to_ref_method', {})
                layer['align_to_ref_method'].setdefault('method_data', {})
                layer['align_to_ref_method']['method_data'].setdefault('win_scale_factor', cfg.DEFAULT_SWIM_WINDOW)
                layer['align_to_ref_method']['method_data'].setdefault('whitening_factor', cfg.DEFAULT_WHITENING)
                if s == self.coarsest_scale_key():
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
                else:
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'



    # def set_defaults_alignment_stack(self, s=None):
    #     if s == None: s = self.scale()
    #     logger.critical(f'caller: {inspect.stack()[1].function}')
    #
    #     for s in self.scales():
    #         scale = self._data['data']['scales'][s]
    #
    #         for layer_index in range(len(scale['alignment_stack'])):
    #             layer = scale['alignment_stack'][layer_index]
    #             layer.setdefault('align_to_ref_method', {})
    #             layer['align_to_ref_method'].setdefault('method_data', {})
    #             layer['align_to_ref_method']['method_data'].setdefault('win_scale_factor', cfg.DEFAULT_SWIM_WINDOW)
    #             layer['align_to_ref_method']['method_data'].setdefault('whitening_factor', cfg.DEFAULT_WHITENING)
    #             if s == self.coarsest_scale_key():
    #                 layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
    #             else:
    #                 layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'

    def sl(self):
        return (self.curScale, self.layer())

    def to_json(self):
        return json.dumps(self._data)

    def to_dict(self):
        return self._data

    def dest(self) -> str:
        return self._data['data']['destination_path']

    def name(self) -> str:
        return os.path.split(self.dest())[-1]


    def set_system_info(self):
        try:    self._data['data']['system']['node'] = platform.node()
        except: self._data['data']['system']['node'] = 'Unknown'


    def base_image_name(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        # logger.info(f'Caller: {inspect.stack()[1].function}, s={s}, l={l}')
        return os.path.basename(self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['filename'])

    def filenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.abspath(l['images']['base']['filename'])
                for l in self._data['data']['scales'][self.scales()[0]]['alignment_stack']])

    def basefilenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.basename(l['images']['base']['filename'])
                for l in self._data['data']['scales'][self.scales()[0]]['alignment_stack']])

    def thumbnail(self, l = None):
        '''Returns absolute path of thumbnail for current layer '''
        if l == None: l = cfg.data.layer()
        return self.thumbnails()[l]

    def thumbnails(self) -> list:
        lst = []
        for name in self.basefilenames():
            lst.append(os.path.join(self.dest(), 'thumbnails', name))
        return lst


    def thumbnails_ref(self) -> list:
        paths = []
        for l in cfg.data.alstack():
            paths.append(os.path.join(self.dest(), 'thumbnails', os.path.basename(l['images']['ref']['filename'])))
        return paths

    def thumbnails_aligned(self) -> list:
        paths = []
        for layer in range(0, self.n_sections()):
            paths.append(os.path.join(self.dest(), self.curScale, 'thumbnails_aligned', self.base_image_name(l=layer)))
        return paths

    def thumbnail_aligned(self):
        '''Returns absolute path of thumbnail for current layer '''
        path = os.path.join(self.dest(), self.curScale, 'thumbnails_aligned', self.base_image_name())
        # return self._data['data']['thumbnails'][self.layer()]
        return path

    def corr_spots_q0(self) -> list:
        names = []
        for img in self.basefilenames():
            # names.append(os.path.join(self.dest(), self.curScale, 'corr_spots' , 'corr_spot_0_' + img))
            names.append(os.path.join(self.dest(), self.curScale, 'thumbnails_corr_spots' , 'corr_spot_0_' + img))
        return names

    def corr_spots_q1(self) -> list:
        names = []
        for img in self.basefilenames():
            # names.append(os.path.join(self.dest(), self.curScale, 'corr_spots' , 'corr_spot_1_' + img))
            names.append(os.path.join(self.dest(), self.curScale, 'thumbnails_corr_spots' , 'corr_spot_1_' + img))
        return names

    def corr_spots_q2(self) -> list:
        names = []
        for img in self.basefilenames():
            # names.append(os.path.join(self.dest(), self.curScale, 'corr_spots' , 'corr_spot_2_' + img))
            names.append(os.path.join(self.dest(), self.curScale, 'thumbnails_corr_spots' , 'corr_spot_2_' + img))
        return names

    def corr_spots_q3(self) -> list:
        names = []
        for img in self.basefilenames():
            # names.append(os.path.join(self.dest(), self.curScale, 'corr_spots', 'corr_spot_3_' + img))
            names.append(os.path.join(self.dest(), self.curScale, 'thumbnails_corr_spots', 'corr_spot_3_' + img))
        return names

    def smallest_scale(self):
        return natural_sort(self._data['data']['scales'].keys())[-1]

    # def thumbnail_names(self):
    #
    #
    #     [os.path.join(cfg.dest())            name in self.basefilenames()])
    #     return glob.glob(os.path.join(self.dest(), 'thumbnails', '*.tif'))

    # def thumbnail_paths(self):
    #     names = self.thumbnail_names()
    #     for i, name in enumerate(names):
    #         names[i] = os.path.join(self.dest(), 'thumbnails', name)

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
        if s == None: s = self.curScale
        return ScaleIterator(self._data['data']['scales'][s]['alignment_stack'][start:end])

    def layer(self) -> int:
        '''Returns the Current Layer as an Integer.'''
        try:
            layer = self._data['data']['current_layer']
            if layer is None:
                logger.warning('Layer is None!')
            return layer
        except:
            logger.warning('Falling Back To Layer 0')
            self.set_layer(0)
            return self._data['data']['current_layer']


    def snr(self, s=None, l=None) -> float:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        if l == 0:
            return 0.0
        try:
            value = self._data['data']['scales'][s]['alignment_stack'][l][
                                                    'align_to_ref_method']['method_results']['snr']
            if isinstance(value, list):
                return statistics.fmean(map(float, value))
        except:
            print_exception()
            logger.warning(f'Unexpected Token For Layer #{l} - Returning 0.0...')
            return 0.0

    def snr_prev(self, s=None, l=None) -> float:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        if l == 0:
            return 0.0
        try:
            value = self._data['data']['scales'][s]['alignment_stack'][l][
                                                    'align_to_ref_method']['previous_method_results']['snr']
            if isinstance(value, list):
                return statistics.fmean(map(float, value))
        except KeyError:
            print_exception()
            logger.warning(f'Unexpected Token For Layer #{l} - Returning 0.0...')
            return 0.0


    def snr_list(self, s=None) -> list[float]:
        # logger.info('caller: %s...' % inspect.stack()[1].function)
        ''' n is 4 for a 2x2 SWIM'''
        try:
            return [self.snr(s=s, l=i) for i in range(len(self))]
        except:
            print_exception()
            logger.error('Unable To Determine SNR List')


    def snr_prev_list(self, s=None, l=None):
        # logger.info('caller: %s...' % inspect.stack()[1].function)
        if s == None: s = self.curScale
        try:
            return [self.snr_prev(s=s, l=i) for i in range(self.n_sections())]
        except:
            print_exception()
            logger.error('Unable To Determine Previous SNR List')


    def snr_components(self, s=None, l=None) -> list[float]:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            return self._data['data']['scales'][s]['alignment_stack'][l][
                            'align_to_ref_method']['method_results']['snr']
        except:
            print_exception()
            return [0.0, 0.0, 0.0, 0.0]


    def snr_prev_components(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = cfg.data.layer()
        try:
            return self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['previous_method_results']['snr_prev']
        except:
            print_exception()
            return [0.0, 0.0, 0.0, 0.0]


    def snr_report(self, s=None, l=None) -> str:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            return self._data['data']['scales'][s]['alignment_stack'][l]['align_to_ref_method']['method_results']['snr_report']
        except KeyError:
            logger.debug('An Exception Was Raised Trying To Get SNR of The Current Layer')
            pass


    def snr_errorbar_size(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        if l == 0:
            return 0.0
        report = self.snr_report(s=s, l=l)
        if not isinstance(report, str):
            logger.debug(f'No SNR Report Available For Layer {l}, Returning 0.0...')
            return 0.0
        substr = '+-'
        return float(report[report.index(substr) + 2: report.index(substr) + 5])


    def snr_errorbars(self, s=None):
        '''Note Length Of Return Array has size self.n_sections() - 1 (!)'''
        if s == None: s = self.curScale
        return np.array([self.snr_errorbar_size(s=s, l=l) for l in range(0, self.n_sections())])


    def check_snr_status(self, s=None) -> list:
        if s == None: s = self.curScale
        unavailable = []
        for i,l in enumerate(self.alstack(s=s)):
            if not 'snr' in l['align_to_ref_method']['method_results']:
                unavailable.append((i, self.name_base(s=s, l=i)))
        return unavailable


    def snr_max_all_scales(self) -> float:
        try:
            #Todo refactor, store local copy, this is a bottleneck
            max_snr = []
            # logger.critical(f'self.scalesAlignedAndGenerated: {self.scalesAlignedAndGenerated}')
            for scale in self.scalesAlignedAndGenerated:
                logger.info(f'scale={scale}')
                try:
                    m = max(self.snr_list(s=scale))
                    # logger.critical(f'm: {m}')
                    max_snr.append(m)
                except:
                    logger.warning('Unable to append maximum SNR, none found')
            # logger.info(f'Returning Max SNR: {max(max_snr)}')
            return max(max_snr)
        except:
            print_exception()


    def snr_average(self, scale=None) -> float:
        logger.info('caller: %s...' % inspect.stack()[1].function)
        if scale == None: scale = self.curScale
        # NOTE: skip the first layer which does not have an SNR value s may be equal to zero
        return statistics.fmean(self.snr_list(s=scale)[1:])


    def snr_prev_average(self, scale=None) -> float:
        logger.info('caller: %s...' % inspect.stack()[1].function)
        if scale == None: scale = self.curScale
        # NOTE: skip the first layer which does not have an SNR value s may be equal to zero
        return statistics.fmean(self.snr_prev_list(s=scale)[1:])


    def print_all_matchpoints(self):
        logger.info('Match Points:')
        for i, l in enumerate(self.alstack()):
            r = l['images']['ref']['metadata']['match_points']
            b = l['images']['base']['metadata']['match_points']
            if r != []:
                logger.info(f'Index: {i}, Ref, Match Points: {str(r)}')
            if b != []:
                logger.info(f'Index: {i}, Base, Match Points: {str(b)}')


    def scale(self) -> str:
        '''Returns the Current Scale as a String.'''
        assert isinstance(self._data['data']['current_scale'], str)
        if self._data['data']['current_scale'] == '':
            logger.warning('WARNING: Scale Was An Empty String')
            self._data['data']['current_scale'] = self.scales()[-1]
        return self._data['data']['current_scale']

    def add_matchpoint(self, coordinates, role, s=None, l=None) -> None:
        '''Example Usage:
             self.add_matchpoint(coordinates=(100, 200), role='base')
        '''
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        logger.info('Adding matchpoint at %s for %s on %s, layer=%d' % (str(coordinates), role, s, l))
        self._data['data']['scales'][s]['alignment_stack'][l]['images'][role]['metadata']['match_points'].append(
            coordinates)
        if role == 'base':
            self._data['data']['scales'][s]['alignment_stack'][l]['align_to_ref_method']['match_points']['src'].append(
                coordinates)
        elif role == 'ref':
            self._data['data']['scales'][s]['alignment_stack'][l]['align_to_ref_method']['match_points']['ref'].append(
                coordinates)


    def match_points(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        layer = self._data['data']['scales'][s]['alignment_stack'][l]
        r = layer['images']['ref']['metadata']['match_points']
        b = layer['images']['base']['metadata']['match_points']
        combined ={'ref': r, 'base': b }
        # logger.info(f'Ref, Match Points: {str(r)}')
        # logger.info(f'Base, Match Points: {str(b)}')
        return combined

    def find_layers_with_matchpoints(self, s=None) -> list:
        '''Returns the list of layers that have match points'''
        if s == None: s = self.curScale
        indexes, names = [], []
        try:
            for i,layer in enumerate(self.alstack()):
                r = layer['images']['ref']['metadata']['match_points']
                b = layer['images']['base']['metadata']['match_points']
                if (r != []) or (b != []):
                    indexes.append(i)
                    names.append(os.path.basename(layer['images']['base']['filename']))
            return list(zip(indexes, names))
        except:
            print_exception()
            logger.warning('Unable to To Return List of Match Point Layers')
            return []

        lst = []
        for i, l in enumerate(self.alstack()):
            r = l['images']['ref']['metadata']['match_points']
            b = l['images']['base']['metadata']['match_points']
            if (r != []) or (b != []):
                lst.append(i)
        return lst

    def print_all_match_points(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        for i,layer in enumerate(self.alstack()):
            r = layer['images']['ref']['metadata']['match_points']
            b = layer['images']['base']['metadata']['match_points']
            if r != [] or b!= []:
                combined = {'ref': r, 'base': b}
                logger.info('____Layer %d Matchpoints____\n  Ref: %s\n  Base: %s' % (i, str(r), str(b)))


    def match_points_ref(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['images']['ref']['metadata']['match_points']

    def match_points_base(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['metadata']['match_points']

    def all_match_points_ref(self, s=None):
        if s == None: s = self.curScale
        lst = []
        for i, layer in enumerate(self.alstack(s=s)):
            mp = layer['images']['ref']['metadata']['match_points']
            if mp != []:
                for p in mp:
                    lst.append([i, p[0], p[1]])
        return lst

    def all_match_points_base(self, s=None):
        if s == None: s = self.curScale
        lst = []
        for i, layer in enumerate(self.alstack(s=s)):
            mp = layer['images']['base']['metadata']['match_points']
            if mp != []:
                for p in mp:
                    lst.append([i, p[0], p[1]])
        return lst

    def get_mps(self, role, s=None):
        if s == None: s = self.curScale
        lst = []
        for i, layer in enumerate(self.alstack(s=s)):
            mp = layer['images'][role]['metadata']['match_points']
            if mp != []:
                for p in mp:
                    lst.append([i, p[0], p[1]])
        return lst

    def annotations(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        layer = self._data['data']['scales'][s]['alignment_stack'][l]
        r = layer['images']['ref']['metadata']['annotations']
        b = layer['images']['base']['metadata']['annotations']
        a = layer['images']['aligned']['metadata']['annotations']
        combined = {'ref': r, 'base': b, 'aligned': a}
        logger.info(f'Ref, Annotations: {str(r)}')
        logger.info(f'Base, Annotations: {str(b)}')
        logger.info(f'Base, Annotations: {str(a)}')
        return combined

    def clear_match_points(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        layer = self._data['data']['scales'][s]['alignment_stack'][l]
        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['match_points'] = []
                # layer['images'][role]['metadata']['annotations'] = []

    def clear_all_match_points(self, s=None, l=None):
        for layer in self.alstack():
            for role in layer['images'].keys():
                if 'metadata' in layer['images'][role]:
                    layer['images'][role]['metadata']['match_points'] = []
                    # layer['images'][role]['metadata']['annotations'] = []

    def clear_annotations(self):
        logger.info("Removing all match points for this l")
        s, l = self.curScale, self.layer()
        layer = self._data['data']['scales'][s]['alignment_stack'][l]
        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['annotations'] = []

    def set_match_points(self, role, matchpoints, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        logger.info("Writing match point to project dictionary")
        if role not in ('ref', 'base', 'aligned'):
            logger.warning('Invalid Role Argument- Returning')
            return
        self._data['data']['scales'][s]['alignment_stack'][l]['images'][role]['metadata']['match_points'] = matchpoints

    def afm(self, s=None, l=None) -> list:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            return self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['affine_matrix']
        except:
            return [[0, 0, 0], [0, 0, 0]]

    def cafm(self, s=None, l=None) -> list:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            return self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['cumulative_afm']
        except:
            return [[0, 0, 0], [0, 0, 0]]

    def afm_list(self, s=None, l=None) -> list:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        lst = [l['align_to_ref_method']['method_results']['affine_matrix'] for l in self.alstack()]
        return lst

    def cafm_list(self, s=None, l=None) -> list:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        lst = [l['align_to_ref_method']['method_results']['cumulative_afm'] for l in self.alstack()]
        return lst

    def bias_data_path(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        return os.path.join(self.dest(), s, 'bias_data')

    def show_afm(self):
        logger.info('\nafm = %s\n' % ' '.join(map(str, self.afm())))

    def show_cafm(self):
        logger.info('\ncafm = %s\n' % ' '.join(map(str, self.cafm())))

    def resolution(self, s=None):
        if s == None: s = self.scale()
        # logger.info('returning: %s' % str(self._data['data']['scales'][s]['resolution']))
        return self._data['data']['scales'][s]['resolution']
    #
    # def res_x(self, s=None) -> int:
    #     if s == None: s = self.curScale
    #     if 'resolution_x' in self._data['data']['scales'][s]:
    #         return int(self._data['data']['scales'][s]['resolution_x'])
    #     else:
    #         logger.warning('resolution_x not in dictionary')
    #         # return int(2)
    #
    # def res_y(self, s=None) -> int:
    #     if s == None: s = self.curScale
    #     if 'resolution_y' in self._data['data']['scales'][s]:
    #         return int(self._data['data']['scales'][s]['resolution_y'])
    #     else:
    #         logger.warning('resolution_y not in dictionary')
    #         # return int(2)
    #
    # def res_z(self, s=None) -> int:
    #     if s == None: s = self.curScale
    #     if 'resolution_z' in self._data['data']['scales'][s]:
    #         return int(self._data['data']['scales'][s]['resolution_z'])
    #     else:
    #         logger.warning('resolution_z not in dictionary')
    #         # return int(50)

    # def set_resolutions(self, scale, res_x:int, res_y:int, res_z:int):
    #     self._data['data']['scales'][scale]['resolution_x'] = res_x
    #     self._data['data']['scales'][scale]['resolution_y'] = res_y
    #     self._data['data']['scales'][scale]['resolution_z'] = res_z

    def set_resolution(self, s, res_x:int, res_y:int, res_z:int):
        self._data['data']['scales'][s]['resolution'] = (res_z, res_y, res_x)

    def cname(self):
        try:     return self._data['data']['cname']
        except:  logger.warning('cname not in dictionary')

    def clevel(self):
        try:     return int(self._data['data']['clevel'])
        except:  logger.warning('clevel not in dictionary')

    def chunkshape(self):
        try:
            return self._data['data']['chunkshape']
        except:
            logger.warning('chunkshape not in dictionary')

    def get_user_zarr_settings(self):
        '''Returns user settings for cname, clevel, chunkshape as tuple (in that order).'''
        return (self.cname(), self.clevel(), self.chunkshape())

    def scale_pretty(self, s=None) -> str:
        if s == None: s = self.curScale
        return 'Scale %d' % self.scale_val(s=s)

    def scale_val(self, s=None) -> int:
        if s == None: s = self.curScale
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

    def n_sections(self) -> int:
        '''Returns # of imported images.
        #TODO Check this for off-by-one bug'''
        try:
            if self.is_mendenhall():
                return cfg.main_window.mendenhall.n_files()
            else:
                return len(self._data['data']['scales']['scale_1']['alignment_stack'])
        except:
            print_exception()

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
        # logger.info('skipped (called By %s)' % inspect.stack()[1].function)

        # print('Before Defaults: s = %s, l = %s' % (str(s), str(l))) # Before Defaults: s = None, l = None
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        # print('After Defaults: s = %s, l = %s' % (str(s), str(l))) # After Defaults: s = scale_4, l = 0
        assert isinstance(s, str)
        assert isinstance(l, int)
        try:
            return bool(self._data['data']['scales'][s]['alignment_stack'][l]['skipped'])
        except IndexError:
            logger.warning(f'Index {l} is out of range.')
        except:
            print_exception()
            logger.warning('Returning False, but there was a problem')
            return False

    def skips_list(self, s=None) -> list:
        '''Returns the list of skipped images for a s'''
        if s == None: s = self.curScale
        indexes, names = [], []
        try:
            for i,layer in enumerate(self.alstack(s=s)):
                if layer['skipped'] == True:
                    indexes.append(i)
                    names.append(os.path.basename(layer['images']['base']['filename']))
            return list(zip(indexes, names))
        except:
            print_exception()
            logger.warning('Unable to To Return Skips List')
            return []

    def skips_indices(self) -> list:
        try:
            return list(list(zip(*cfg.data.skips_list()))[0])
        except:
            return []

    def skips_by_name(self, s=None) -> list[str]:
        '''Returns the list of skipped images for a s'''
        if s == None: s = self.curScale
        lst = []
        try:
            for i in range(self.n_sections()):
                if self._data['data']['scales'][s]['alignment_stack'][i]['skipped'] == True:
                    f = os.path.basename(self._data['data']['scales'][s]['alignment_stack'][i][
                                             'images']['base']['filename'])
                    lst.append(f)
            return lst
        except:
            logger.warning('Unable to To Return Skips By Name List')
            return []

    def whitening(self) -> float:
        '''Returns the Whitening Factor for the Current Layer.'''
        return float(self._data['data']['scales'][self.curScale]['alignment_stack'][
                         self.layer()]['align_to_ref_method']['method_data']['whitening_factor'])

    def swim_window(self) -> float:
        '''Returns the SWIM Window for the Current Layer.'''
        return float(self._data['data']['scales'][self.curScale]['alignment_stack'][
                         self.layer()]['align_to_ref_method']['method_data']['win_scale_factor'])

    def has_bb(self, s=None) -> bool:
        '''Returns the Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.curScale
        return bool(self._data['data']['scales'][s]['use_bounding_rect'])

    def bounding_rect(self, s=None):
        if s == None: s = self.curScale
        try:
            return self._data['data']['scales'][s]['bounding_rect']
        except:
            try:
                self.set_bounding_rect(ComputeBoundingRect(self.alstack(s=s), scale=s))
                return self._data['data']['scales'][s]['bounding_rect']
            except:
                logger.warning('Unable to return a bounding rect (s=%s)' % s)
                return None

    def image_size(self, s=None):
        if s == None: s = self.curScale
        logger.debug('Called by %s, s=%s' % (inspect.stack()[1].function, s))
        try:
            return self._data['data']['scales'][s]['image_src_size']
        except:
            logger.info(f"No key 'image_src_size' found (scale:{s}). Adding it now...")
            try:
                self.set_image_size(s=s)
                answer = self._data['data']['scales'][s]['image_src_size']
                logger.info(f'Returning {answer}')
                return answer
            except:
                print_exception()
                logger.warning('Unable to return the image size (s=%s)' % s)
                return None

    def full_scale_size(self):
        return ImageSize(self.path_base(s='scale_1'))

    def poly_order(self, s=None) -> int:
        '''Returns the Polynomial Order for the Current Scale.'''
        if s == None: s = self.curScale
        return int(self._data['data']['scales'][s]['poly_order'])

    def null_cafm(self, s=None) -> bool:
        '''Gets the Null Cafm Trends On/Off State for the Current Scale.'''
        if s == None: s = self.curScale
        return bool(self._data['data']['scales'][s]['null_cafm_trends'])

    def al_option(self, s=None) -> str:
        '''Gets the Alignment Option for the Current Scale.'''
        if s == None: s = self.curScale
        return self._data['data']['scales'][s]['method_data']['alignment_option']

    def path_ref(self, s=None, l=None) -> str:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['images']['ref']['filename']

    def path_base(self, s=None, l=None) -> str:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        # Todo -- Refactor!
        try:
            name = self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['filename']
            return name
        except:
            print_exception()

    def name_base(self, s=None, l=None) -> str:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            return os.path.basename(self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['filename'])
        except:
            return ''

    def name_ref(self, s=None, l=None) -> str:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            return os.path.basename(self._data['data']['scales'][s]['alignment_stack'][l]['images']['ref']['filename'])
        except:
            return ''

    def path_aligned(self, s=None, l=None) -> str:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        return os.path.join(self.dest(), s, 'img_aligned', self.name_base(l=l))

    def zarr_scale_paths(self):
        l = []
        for s in self.scales():
            # l.append(os.path.join(self._data['data']['destination_path'], s + '.zarr'))
            l.append(os.path.join(self._data['data']['destination_path'], 'img_src.zarr', s + str(get_scale_val(s))))
        return l

    def roles(self):
        l, s = self.layer(), self.curScale
        return self._data['data']['scales'][s]['alignment_stack'][l]['images'].keys()

    def set_destination(self, s):
        self._data['data']['destination_path'] = s

    def set_scale(self, s:str) -> None:
        '''Sets the Current Scale.'''
        self._data['data']['current_scale'] = s
        self.curScale = s

    def set_layer(self, index:int) -> None:
        '''Sets Current Layer To Index.'''
        assert isinstance(index, int)
        # logger.info(f'Viewing #{index}, {self.curScale}')
        self._data['data']['current_layer'] = index

    def set_previous_results(self, s=None):
        logger.info('Setting PREVIOUS SNR, caller: %s...' % inspect.stack()[1].function)
        if s == None: s = self.curScale
        logger.info('')
        try:
            for l in range(len(self)):
                self._data['data']['scales'][s]['alignment_stack'][l][
                    'align_to_ref_method']['previous_method_results'] = \
                    self._data['data']['scales'][s]['alignment_stack'][l][
                        'align_to_ref_method']['method_results']
        except:
            print_exception()
            logger.warning('Unable to set previous SNR...')

    def set_skip(self, b: bool, s=None, l=None) -> None:
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['data']['scales'][s]['alignment_stack'][l]['skipped'] = b

    def set_whitening(self, f: float) -> None:
        '''Sets the Whitening Factor for the Current Layer.'''
        self._data['data']['scales'][self.curScale]['alignment_stack'][self.layer()][
            'align_to_ref_method']['method_data']['whitening_factor'] = f

    def set_swim_window(self, f: float) -> None:
        '''Sets the SWIM Window for the Current Layer.'''
        self._data['data']['scales'][self.curScale]['alignment_stack'][self.layer()][
            'align_to_ref_method']['method_data']['win_scale_factor'] = f

    def set_use_bounding_rect(self, b: bool, s=None) -> None:
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None:
            for s in self.scales():
                self._data['data']['scales'][s]['use_bounding_rect'] = bool(b)
        else:
            self._data['data']['scales'][s]['use_bounding_rect'] = bool(b)

    def set_bounding_rect(self, bounding_rect: list, s=None) -> None:
        if s == None: s = self.curScale
        self._data['data']['scales'][s]['bounding_rect'] = bounding_rect

    def set_calculate_bounding_rect(self, s=None):
        if s == None: s = self.curScale
        self.set_bounding_rect(ComputeBoundingRect(self.alstack(s=s)))
        return self.bounding_rect()

    def set_image_size(self, s) -> None:
        self._data['data']['scales'][s]['image_src_size'] = ImageSize(self.path_base(s=s))
        val = self._data['data']['scales'][s]['image_src_size']
        # logger.info(f'Just Set {s} image size to {val}')
        logger.info(f'Scale Image Sizes Resolved, {self.scale_pretty(s=s)}: {self.image_size(s=s)}')

    def set_image_size_directly(self, size, s=None):
        if s == None: s = self.curScale
        logger.info(f"Setting Image Sizes Directly, {s}, ImageSize: {size}")
        self._data['data']['scales'][s]['image_src_size'] = size

    def set_poly_order(self, x: int) -> None:
        '''Sets the Polynomial Order for the Current Scale.'''
        self._data['data']['scales'][self.curScale]['poly_order'] = int(x)

    def set_use_poly_order(self, b: bool) -> None:
        '''Sets the Null Cafm Trends On/Off State for the Current Scale.'''
        self._data['data']['scales'][self.curScale]['null_cafm_trends'] = bool(b)

    # def make_absolute(file_path, proj_path):
    #     abs_path = os.path.join(os.path.split(proj_path)[0], file_path)
    #     return abs_path

    def set_al_dict(self, aldict, s=None):
        if s == None: s = self.curScale
        try:
            self._data['data']['scales'][s]['alignment_stack'] = aldict
        except:
            logger.warning('Unable to set alignment dict')

    def remove_aligned(self, scale, start_layer):
        '''
        Removes previously generated aligned images for the current s, starting at l 'start_layer'.
        :param use_scale: The s to remove aligned images from.
        :type use_scale: str

        :param start_layer: The starting l index from which to remove all aligned images, defaults to 0.
        :type start_layer: int
        '''
        cfg.main_window.hud.post(f'Removing Aligned for Current Scale...')
        try:
            for layer in self._data['data']['scales'][scale]['alignment_stack'][start_layer:]:
                ifn = layer['images'].get('filename', None)
                layer['images'].pop('aligned', None)
                if ifn != None:
                    try:     os.remove(ifn)
                    except:  logger.warning(f'os.remove({ifn}) Raised An Exception')
        except:
            print_exception()
            cfg.main_window.warn('An Exception Was Raisied While Removing Previous Alignment...')
        else:
            cfg.main_window.hud.done()

    def set_afm(self, afm: list, s=None, l=None) -> None:
        '''set afm as list of lists of floats'''
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['cumulative_afm'] = afm
        except:
            print_exception()

    def set_cafm(self, cafm: list, s=None, l=None) -> None:
        '''set cafm as list of lists of floats'''
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        try:
            self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['cumulative_afm'] = cafm
        except:
            print_exception()

    def selected_method(self, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['align_to_ref_method']['selected_method']

    def set_selected_method(self, method, s=None, l=None):
        if s == None: s = self.curScale
        if l == None: l = self.layer()
        self._data['data']['scales'][s]['alignment_stack'][l]['align_to_ref_method']['selected_method'] = method


    def set_destination_absolute(self, head):
        head = os.path.split(head)[0]
        self.set_destination(os.path.join(head, self.dest()))

    def set_paths_absolute(self, filename):
        logger.info(f'Setting Absolute File Paths...')
        # returns path to project file minus extension (should be the project directory)
        self.set_destination(os.path.splitext(filename)[0])
        logger.debug(f'Setting absolute project dest/head: {self.dest()}...')
        try:
            head = self.dest() # returns parent directory
            for s in self.scales():
                if s == 'scale_1':
                    pass
                else:
                    for l in self._data['data']['scales'][s]['alignment_stack']:
                        for r in l['images'].keys():
                            # if (not l==0) and (not r=='ref'):
                            tail = l['images'][r]['filename']
                            l['images'][r]['filename'] = os.path.join(head, tail)
                    # self._data['data']['scales'][s]['alignment_stack'][0]['images']['ref']['filename'] = None
        except:
            logger.warning('Setting Absolute Paths Triggered This Exception')
            print_exception()


    def alstack(self, s=None) -> dict:
        if s == None: s = self.scale()
        return self._data['data']['scales'][s]['alignment_stack']


    def aligned_list(self) -> list[str]:
        '''Deprecate this

        Get aligned scales list. Check project datamodel and aligned Zarr group presence.'''
        lst = []
        for s in self.scales():
            r = self._data['data']['scales'][s]['alignment_stack'][-1]['align_to_ref_method']['method_results']
            if r != {}:
                lst.append(s)
        for s in lst:
            if not exist_aligned_zarr(s):
                lst.remove(s)
        return lst

    # def not_aligned_list(self) -> list[str]:
    #     '''Get not aligned scales list.'''
    #     lst = []
    #     for s in self.scales():
    #         if not exist_aligned_zarr(s):
    #             lst.append(s)
    #     logger.debug('Not Aligned Scales List: %s ' % str(lst))
    #     return lst

    def not_aligned_list(self):
        return set(self.scales()) - set(self.scalesAlignedAndGenerated)

    def coarsest_scale_key(self) -> str:
        '''Return the coarsest s key. '''
        return natural_sort([key for key in self._data['data']['scales'].keys()])[-1]

    def next_coarsest_scale_key(self) -> str:
        if self.n_scales() == 1:
            return self.curScale
        scales_dict = self._data['data']['scales']
        cur_scale_key = self.curScale
        coarsest_scale = list(scales_dict.keys())[-1]
        if cur_scale_key == coarsest_scale:
            return cur_scale_key
        scales_list = []
        for scale_key in scales_dict.keys():
            scales_list.append(scale_key)
        cur_scale_index = scales_list.index(cur_scale_key)
        next_coarsest_scale_key = scales_list[cur_scale_index + 1]
        return next_coarsest_scale_key

    def is_alignable(self) -> bool:
        '''Checks if the current scale is able to be aligned'''
        try:
            if self.nSections < 1:
                logger.debug("Returning False because self.nSections < 1")
                return False
            scales_list = self.scales()
            cur_scale_key = self.curScale
            coarsest_scale = scales_list[-1]
            if cur_scale_key == coarsest_scale:
                logger.debug("is_alignable returning True because: "
                             "cur_scale_key == coarsest_scale) is True")
                return True
            cur_scale_index = scales_list.index(cur_scale_key)
            next_coarsest_scale_key = scales_list[cur_scale_index + 1]
            if not cfg.data.is_aligned(s=next_coarsest_scale_key):
                logger.debug("is_alignable returning False because: "
                             "not exist_aligned_zarr(next_coarsest_scale_key) is True")
                return False
            else:
                logger.debug('Returning True')
                return True
        except:
            print_exception()

    def clear_all_skips(self):
        cfg.main_window.tell('Resetting Skips...')
        try:
            for scale in self.scales():
                scale_key = str(scale)
                for layer in self._data['data']['scales'][scale_key]['alignment_stack']:
                    layer['skipped'] = False
        except:
            print_exception()

    def append_image(self, file):
        scale = self.scale()
        # logger.debug("Adding Image: %s, role: base, scale: %s" % (file, scale))
        used_for_this_role = ['base' in l['images'].keys() for l in self.alstack(s=scale)]
        # logger.info(f'used_for_this_role = {used_for_this_role}')
        # used_for_this_role = [True, True, True, True]
        if False in used_for_this_role:
            layer_index = used_for_this_role.index(False)
            logger.critical(f'(!!!) "False in used_for_this_role" layer_index: {layer_index}')
        else:
            self._data['data']['scales'][scale]['alignment_stack'].append(copy.deepcopy(layer_template))
            '''copy from template'''
            layer_index = self.n_sections() - 1
        self.add_img_base(scale=scale, layer=layer_index, filename=file)
        self.add_img_ref(scale=scale, layer=layer_index, filename='')

    def append_empty(self):
        logger.critical('MainWindow.append_empty:')
        scale = self.curScale
        used_for_this_role = ['base' in l['images'].keys() for l in self.alstack(s=scale)]
        layer_index = -1
        if False in used_for_this_role:
            layer_index = used_for_this_role.index(False)
        else:
            self._data['data']['scales'][scale]['alignment_stack'].append(copy.deepcopy(layer_template))
            layer_index_for_new_role = len(self['data']['scales'][scale]['alignment_stack']) - 1
        self.add_img_base(scale=scale, layer=layer_index, filename='')

    def add_img_ref(self, scale, layer, filename=''):
        self._data['data']['scales'][scale]['alignment_stack'][layer]['images']['ref'] = copy.deepcopy(image_template)
        self._data['data']['scales'][scale]['alignment_stack'][layer]['images']['ref']['filename'] = filename
        self._data['data']['scales'][scale]['alignment_stack'][layer]['reference'] = filename          # 0119+

    def add_img_base(self, scale, layer, filename=''):
        self._data['data']['scales'][scale]['alignment_stack'][layer]['images']['base'] = copy.deepcopy(image_template)
        self._data['data']['scales'][scale]['alignment_stack'][layer]['images']['base']['filename'] = filename
        self._data['data']['scales'][scale]['alignment_stack'][layer]['filename'] = filename          # 0119+


    # def add_img(self, scale, layer, role, filename=''):
    #     logger.info(f'Adding Image ({scale}, {layer}, {role}): {filename}...')
    #     self._data['data']['scales'][scale]['alignment_stack'][layer]['images'][role] = copy.deepcopy(image_template)
    #     self._data['data']['scales'][scale]['alignment_stack'][layer]['images'][role]['filename'] = filename
    #     self._data['data']['scales'][scale]['alignment_stack'][layer]['img'] = copy.deepcopy(image_template) # 0119+
    #     self._data['data']['scales'][scale]['alignment_stack'][layer]['img'] = filename                      # 0119+


    def update_datamodel(self, updated_model):
        '''This function is called by align_layers and regenerate_aligned. It is called when
        'run_json_project' returns with need_to_write_json=false'''
        logger.info('Updating Data Model...')
        # Load the alignment stack after the alignment has completed
        aln_image_stack = []
        scale = self.curScale
        for layer in self.alstack():
            image_name = None
            if 'base' in layer['images'].keys():
                image_name = layer['images']['base']['filename']
            # Convert from the base name to the standard aligned name:
            name = None
            if image_name is not None:
                if scale == "scale_1":
                    name = os.path.join(os.path.abspath(self._data['data']['destination_path']),
                                        scale, 'img_aligned', os.path.split(image_name)[-1])
                else:
                    name_parts = os.path.split(image_name)
                    if len(name_parts) >= 2:
                        name = os.path.join(os.path.split(name_parts[0])[0], os.path.join('img_aligned', name_parts[1]))
            aln_image_stack.append(name)
            logger.info("Adding aligned image %s" % name)
            layer['images']['aligned'] = {}
            layer['images']['aligned']['filename'] = name
        try:
            cfg.main_window.load_images_in_role('aligned', aln_image_stack)
        except:
            print_exception()

    def are_there_any_skips(self) -> bool:
        if len(self.skips_list()) > 0:
            return True
        else:
            return False

    def set_method_options(self):
        coarsest = self.coarsest_scale_key()
        for s in self.scales():
            if s == coarsest:  self._data['data']['scales'][s]['method_data']['alignment_option'] = 'init_affine'
            else:  self._data['data']['scales'][s]['method_data']['alignment_option'] = 'refine_affine'
            for i in range(self.n_scales()):
                layer = self._data['data']['scales'][s]['alignment_stack'][i]
                if s == coarsest:
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
                else:
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'



    def set_scales_from_string(self, scale_string: str):
        '''This is not pretty. Needs to be refactored ASAP.
        Two callers: 'new_project', 'prepare_generate_scales_worker'
        '''
        logger.info('')
        cur_scales = list(map(str, cfg.data.scale_vals()))
        try:
            input_scales = [str(v) for v in sorted([get_scale_val(s) for s in scale_string.strip().split(' ')])]
        except:
            logger.error(f'Bad input: {scale_string}. Scales Unchanged.')
            input_scales = []
        if (input_scales != cur_scales):
            input_scale_keys = [get_scale_key(v) for v in input_scales]
            scales_to_remove = list(set(self.scales()) - set(input_scale_keys) - {'scale_1'})
            logger.info(f'Removing Scale Keys: {scales_to_remove}...')
            for key in scales_to_remove:
                self._data['data']['scales'].pop(key)
            scales_to_add = list(set(input_scale_keys) - set(self.scales()))
            logger.info(f'Adding Scale Keys (copying from scale_1): {scales_to_add}...')
            for key in scales_to_add:
                new_stack = [deepcopy(l) for l in self.alstack(s='scale_1')]
                self._data['data']['scales'][key] = \
                    {'alignment_stack': new_stack, 'method_data': { 'alignment_option': 'init_affine' } }

    # def set_default_data(self):
    #     '''Ensure Proper Data Structure (that the previewmodel is usable)...'''
    #     logger.debug('Ensuring called by %s' % inspect.stack()[1].function)
    #     '''  '''
    #     scales_dict = self._data['data']['scales']
    #     coarsest = list(scales_dict.keys())[-1]
    #     for scale_key in scales_dict.keys():
    #         scale = scales_dict[scale_key]
    #         scale.setdefault('use_bounding_rect', cfg.DEFAULT_BOUNDING_BOX)
    #         scale.setdefault('null_cafm_trends', cfg.DEFAULT_NULL_BIAS)
    #         scale.setdefault('poly_order', cfg.DEFAULT_POLY_ORDER)
    #         for layer_index in range(len(scale['alignment_stack'])):
    #             layer = scale['alignment_stack'][layer_index]
    #             layer.setdefault('align_to_ref_method', {})
    #             layer['align_to_ref_method'].setdefault('method_data', {})
    #             layer['align_to_ref_method']['method_data'].setdefault('win_scale_factor', cfg.DEFAULT_SWIM_WINDOW)
    #             layer['align_to_ref_method']['method_data'].setdefault('whitening_factor', cfg.DEFAULT_WHITENING)
    #             if scale_key == coarsest:
    #                 layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
    #             else:
    #                 layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'


    def link_reference_sections(self):
        '''Called by the functions '_callbk_skipChanged' and 'import_multiple_images'
        Link layers, taking into accounts skipped layers'''
        # self.set_default_data()  # 0712 #0802 #original
        for s in self.scales():
            skip_list = self.skips_indices()
            for layer_index in range(len(self)):
                base_layer = self._data['data']['scales'][s]['alignment_stack'][layer_index]
                if (layer_index == 0) or (layer_index in skip_list):
                    self.add_img_ref(scale=s, layer=layer_index, filename='')
                else:
                    j = layer_index - 1  # Find nearest previous non-skipped l
                    while (j in skip_list) and (j >= 0):
                        j -= 1
                    if (j not in skip_list) and (j >= 0):
                        ref = self._data['data']['scales'][s]['alignment_stack'][j]['images']['base']['filename']
                        ref = os.path.join(self.dest(), s, 'img_src', ref)
                        base_layer['images']['ref']['filename'] = ref
                        base_layer['reference'] = ref


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
                    stack = scale['alignment_stack']
                    current_alignment_options = []
                    for layer in stack:
                        if "align_to_ref_method" in layer:
                            align_method = layer['align_to_ref_method']
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
                    stack = scale['alignment_stack']
                    current_alignment_options = []
                    for layer in stack:
                        if "align_to_ref_method" in layer:
                            align_method = layer['align_to_ref_method']
                            if 'method_data' in align_method:
                                if 'alignment_option' in align_method['method_data']:
                                    align_method['method_data'].pop('alignment_option')
                # Now the datamodel previewmodel is at 0.28, so give it the appropriate version
                self._data['version'] = 0.28

            if self._data['version'] == 0.28:
                print("\n\nUpgrading datamodel previewmodel from " + str(self._data['version']) + " to " + str(0.29))
                # Need to modify the datamodel previewmodel from 0.28 up to 0.29
                # The "use_c_version" was added to the "user_settings" dictionary
                self._data['user_settings']['use_c_version'] = True
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
                    stack = scale['alignment_stack']
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

    # def update_init_rot(self):
    #     image_scales_to_run = [self.scale_val(s) for s in sorted(self._data['data']['scales'].keys())]
    #     for s in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #         scale_key = self.get_scale_key(s)
    #         for i, l in enumerate(self._data['data']['scales'][scale_key]['alignment_stack']):
    #             l['align_to_ref_method']['method_options'] = {'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION}
    #     logger.critical('cfg.DEFAULT_INITIAL_ROTATION = %f' % cfg.DEFAULT_INITIAL_ROTATION)
    #
    # def update_init_scale(self):
    #     image_scales_to_run = [self.scale_val(s) for s in sorted(self._data['data']['scales'].keys())]
    #     for s in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #         scale_key = self.get_scale_key(s)
    #         for i, l in enumerate(self._data['data']['scales'][scale_key]['alignment_stack']):
    #             l['align_to_ref_method']['method_options'] = {'initial_scale': cfg.DEFAULT_INITIAL_SCALE}
    #     logger.critical('cfg.DEFAULT_INITIAL_SCALE = %f' % cfg.DEFAULT_INITIAL_SCALE)

    def clear_method_results(self, scale, start, end):
        logger.info("Clearing 'method_results'...")
        for layer in self._data['data']['scales'][scale]['alignment_stack'][start:end]:
            layer['align_to_ref_method']['method_results'] = {}

    def make_paths_relative(self, start):
        self.set_destination(os.path.relpath(self.dest(), start=start))
        for s in self.downscales():
            for layer in self.alstack(s=s):
                for role in layer['images'].keys():
                    filename = layer['images'][role]['filename']
                    if filename != '':
                        layer['images'][role]['filename'] = os.path.relpath(filename, start=start)


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

'''
# layer_dict as defined in run_project_json.py:
layer_dict = {
    "images": {
        "base": {
            "metadata": {
                "match_points": match_points[0]
            }
        },
        "ref": {
            "metadata": {
                "match_points": match_points[1]
            }
        }
    },
    "align_to_ref_method": {
        "selected_method": "Match Point Align",
        "method_options": [
            "Auto Swim Align",
            "Match Point Align"
        ],
        "method_data": {},
        "method_results": {}
    }
}
'''

'''

print('Before Defaults: s = %s, l = %s' % (str(s), str(l)))
print('After Defaults: s = %s, l = %s' % (str(s), str(l)))

'''
