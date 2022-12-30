#!/usr/bin/env python3

"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""
import os
import json
import glob
import inspect
import logging
import statistics
from copy import deepcopy
from dataclasses import dataclass
import src.config as cfg
from src.data_structs import data_struct
from src.helpers import print_exception, natural_sort, are_images_imported, is_arg_scale_aligned, get_scale_key, \
    get_scale_val
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
    """ Encapsulate data previewmodel dictionary and wrap with methods for convenience """

    def __init__(self, data=None, name='', mendenhall=False):
        logger.info('Constructing Data Model...')
        self._current_version = 0.40

        if data:
            self._data = data
        else:
            self._data = data_struct
            self._data['data']['destination_path'] = name

        if self.layer() == None:
            self.set_layer(0)

        self._data['data']['mendenhall'] = mendenhall

        self.scalesAligned = []
        self.nScalesAligned = None
        self.nscales = None
        self.nlayers = None

        self._data['user_settings'].setdefault('mp_marker_size', cfg.MP_SIZE)
        self._data['user_settings'].setdefault('mp_marker_lineweight', cfg.MP_LINEWEIGHT)
        self._data['data'].setdefault('cname', cfg.CNAME)
        self._data['data'].setdefault('clevel', cfg.CLEVEL)
        self._data['data'].setdefault('chunkshape', (cfg.CHUNK_Z, cfg.CHUNK_Y, cfg.CHUNK_X))

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
            return self.n_layers()
        except:
            logger.warning('No Images Found')

    def sl(self):
        return (self.scale(), self.layer())

    def to_json(self):
        return json.dumps(self._data)

    def to_dict(self):
        return self._data

    def dest(self) -> str:
        return self._data['data']['destination_path']

    def name(self) -> str:
        return os.path.split(cfg.data.dest())[-1]

    def base_image_name(self, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        return os.path.basename(self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['filename'])

    def filenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.abspath(l['images']['base']['filename'])
                for l in self._data['data']['scales'][self.scales()[0]]['alignment_stack']])

    def basefilenames(self):
        '''Returns filenames as absolute paths'''
        return natural_sort([os.path.basename(l['images']['base']['filename'])
                for l in self._data['data']['scales'][self.scales()[0]]['alignment_stack']])

    # def thumbnail_names(self):
    #
    #
    #     [os.path.join(cfg.dest())            name in self.basefilenames()])
    #     return glob.glob(os.path.join(self.dest(), 'thumbnails', '*.tif'))
    def thumbnails(self) -> list:
        return self._data['data']['thumbnails']

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

    def get_iter(self, s=None):
        if s == None: s = cfg.data.scale()
        return ScaleIterator(self._data['data']['scales'][s]['alignment_stack'])

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

    # def snr(self) -> str:
    #     '''TODO This probably shouldn't return a string'''
    #     if not self._data['data']['current_scale']:
    #         logger.warning("Can't Get SNR Because Scale is Not Set")
    #         return ''
    #     try:
    #         s = self._data['data']['current_scale']
    #         l = self._data['data']['current_layer']
    #         if len(self._data['data']['scales']) > 0:
    #             scale = self._data['data']['scales'][s]
    #             if len(scale['alignment_stack']) > 0:
    #                 layer = scale['alignment_stack'][l]
    #                 if 'align_to_ref_method' in layer:
    #                     if 'method_results' in layer['align_to_ref_method']:
    #                         method_results = layer['align_to_ref_method']['method_results']
    #                         if 'snr_report' in method_results:
    #                             if method_results['snr_report'] != None:
    #                                 curr_snr = method_results['snr_report']
    #                                 logger.debug("  returning the current snr: %s" % str(curr_snr))
    #                                 return str(curr_snr)
    #     except:
    #         logger.warning('An Exception Was Raised Trying To Get SNR of The Current Layer')
    #
    # def snr_list(self, s=None):
    #     if s == None: s = self.scale()
    #     snr_lst = []
    #     for layer in self._data['data']['scales'][s]['alignment_stack']:
    #         try:
    #             snr_vals = layer['align_to_ref_method']['method_results']['snr']
    #             mean_snr = sum(snr_vals) / len(snr_vals)
    #             snr_lst.append(mean_snr)
    #         except:
    #             pass
    #     return snr_lst


    def snr(self, s=None, l=None) -> float:
        '''TODO This probably shouldn't return a string'''
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        if l == 0:
            return 0.0
        try:
            conv_float = map(float, self._data['data']['scales'][s]['alignment_stack'][l]
                                               ['align_to_ref_method']['method_results']['snr'])
            return statistics.fmean(conv_float)
        except:
            # logger.warning('An Exception Was Raised Trying To Get SNR of The Current Layer')
            logger.error(f'No SNR Data Was Found For Layer {i}...')
            logger.error(f'  Base : {self.name_base(s=s, l=i)}')
            logger.error(f'  Ref  : {self.name_ref(s=s, l=i)}')
            logger.error(f'  Returning 0.00')
            return 0.0


    def snr_list(self, s=None) -> list[float]:
        logger.info('Caller: %s' % inspect.stack()[1].function)
        if s == None: s = self.scale()
        # n should be 16 for layers except for index 0 which equals [0.0]
        try:
            lst = [self.snr(s=s, l=i) for i in range(0, self.n_layers())]
            return lst
        except:
            print_exception()
            logger.error('Unable To Determine SNR List')
            return []



    def snr_max_all_scales(self) -> float:
        #Todo refactor, store local copy, this is a bottleneck
        max_snr = []
        # logger.critical(f'self.scalesAligned: {self.scalesAligned}')
        for scale in self.scalesAligned:
            try:
                m = max(self.snr_list(s=scale))
                # logger.critical(f'm: {m}')
                max_snr.append(m)
            except:
                logger.warning('Unable to append maximum SNR, none found')
        # logger.info(f'Returning Max SNR: {max(max_snr)}')
        return max(max_snr)


    def snr_average(self, scale=None) -> float:
        logger.info('caller: %s...' % inspect.stack()[1].function)
        if scale == None: scale = cfg.data.scale()
        # NOTE: skip the first layer which does not have an SNR value s may be equal to zero
        return statistics.fmean(self.snr_list(s=scale)[1:])


    def snr_report(self, s=None, l=None) -> str:
        '''TODO This probably shouldn't return a string'''
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        try:
            return str(self._data['data']['scales'][s]['alignment_stack'][l]
                       ['align_to_ref_method']['method_results']['snr_report'])
        except:
            logger.warning('An Exception Was Raised Trying To Get SNR of The Current Layer')


    def print_all_matchpoints(self):
        logger.info('Match Points:')
        for i, l in enumerate(self.alstack()):
            r = l['images']['ref']['metadata']['match_points']
            b = l['images']['base']['metadata']['match_points']
            if r != []:
                logger.info(f'Index: {i}, Ref, Match Points: {str(r)}')
            if b != []:
                logger.info(f'Index: {i}, Base, Match Points: {str(b)}')

    # def find_layers_with_skips(self):
    #     lst = []
    #     for i, l in enumerate(self.alstack()):
    #         r = l['images']['ref']['metadata']['match_points']
    #         b = l['images']['base']['metadata']['match_points']
    #         if (r != []) or (b != []):
    #             lst.append(i)
    #     return lst

    def scale(self) -> str:
        '''Returns the Current Scale as a String.'''
        assert isinstance(self._data['data']['current_scale'], str)
        if self._data['data']['current_scale'] == '':
            logger.warning('WARNING: Scale Was An Empty String')
            self._data['data']['current_scale'] = cfg.data.scales()[-1]
        return self._data['data']['current_scale']

    def add_matchpoint(self, coordinates, role, s=None, l=None) -> None:
        '''Example Usage:
             cfg.data.add_matchpoint(coordinates=(100, 200), role='base')
        '''
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        logger.info('Adding matchpoint at %s for %s on %s, layer=%d' % (str(coordinates), role, s, l))
        self._data['data']['scales'][s]['alignment_stack'][l]['images'][role]['metadata']['match_points'].append(
            coordinates
        )

    def match_points(self, s=None, l=None):
        if s == None: s = self.scale()
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
        if s == None: s = self.scale()
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
            logger.warning('Unable to To Return List of Match Point Layers');
            return []

        lst = []
        for i, l in enumerate(self.alstack()):
            r = l['images']['ref']['metadata']['match_points']
            b = l['images']['base']['metadata']['match_points']
            if (r != []) or (b != []):
                lst.append(i)
        return lst

    def print_all_match_points(self, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        for i,layer in enumerate(self.alstack()):
            r = layer['images']['ref']['metadata']['match_points']
            b = layer['images']['base']['metadata']['match_points']
            if r != [] or b!= []:
                combined = {'ref': r, 'base': b}
                logger.info('____Layer %d Matchpoints____\n  Ref: %s\n  Base: %s' % (i, str(r), str(b)))


    def match_points_ref(self, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['images']['ref']['metadata']['match_points']

    def match_points_base(self, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['metadata']['match_points']

    def all_match_points_ref(self, s=None):
        if s == None: s = self.scale()
        lst = []
        for i, layer in enumerate(self.alstack(s=s)):
            mp = layer['images']['ref']['metadata']['match_points']
            if mp != []:
                for p in mp:
                    lst.append([i, p[0], p[1]])
        return lst

    def all_match_points_base(self, s=None):
        if s == None: s = self.scale()
        lst = []
        for i, layer in enumerate(self.alstack(s=s)):
            mp = layer['images']['base']['metadata']['match_points']
            if mp != []:
                for p in mp:
                    lst.append([i, p[0], p[1]])
        return lst

    def get_mps(self, role, s=None):
        if s == None: s = self.scale()
        lst = []
        for i, layer in enumerate(self.alstack(s=s)):
            mp = layer['images'][role]['metadata']['match_points']
            if mp != []:
                for p in mp:
                    lst.append([i, p[0], p[1]])
        return lst

    def annotations(self, s=None, l=None):
        if s == None: s = self.scale()
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
        if s == None: s = self.scale()
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
        s, l = self.scale(), self.layer()
        layer = self._data['data']['scales'][s]['alignment_stack'][l]
        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['annotations'] = []

    def set_match_points(self, role, matchpoints, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        logger.info("Writing match point to project dictionary")
        if role not in ('ref', 'base', 'aligned'):
            logger.warning('Invalid Role Argument- Returning')
            return
        self._data['data']['scales'][s]['alignment_stack'][l]['images'][role]['metadata']['match_points'] = matchpoints

    def afm(self, s=None, l=None) -> list:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        try:
            return self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['affine_matrix']
        except:
            return [[0, 0, 0], [0, 0, 0]]

    def cafm(self, s=None, l=None) -> list:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        try:
            return self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['cumulative_afm']
        except:
            return [[0, 0, 0], [0, 0, 0]]

    def afm_list(self, s=None, l=None) -> list:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        lst = [l['align_to_ref_method']['method_results']['affine_matrix'] for l in self.alstack()]
        return lst

    def cafm_list(self, s=None, l=None) -> list:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        lst = [l['align_to_ref_method']['method_results']['cumulative_afm'] for l in self.alstack()]
        return lst

    def bias_data_path(self, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        return os.path.join(cfg.data.dest(), s, 'bias_data')

    def show_afm(self):
        cfg.main_window.hud('\nafm = %s\n' % ' '.join(map(str, self.afm())))

    def show_cafm(self):
        cfg.main_window.hud('\ncafm = %s\n' % ' '.join(map(str, self.cafm())))

    def res_x(self, s=None) -> int:
        if s == None: s = self.scale()
        if 'resolution_x' in self._data['data']['scales'][s]:
            return int(self._data['data']['scales'][s]['resolution_x'])
        else:
            logger.warning('resolution_x not in dictionary')
            # return int(2)

    def res_y(self, s=None) -> int:
        if s == None: s = self.scale()
        if 'resolution_y' in self._data['data']['scales'][s]:
            return int(self._data['data']['scales'][s]['resolution_y'])
        else:
            logger.warning('resolution_y not in dictionary')
            # return int(2)

    def res_z(self, s=None) -> int:
        if s == None: s = self.scale()
        if 'resolution_z' in self._data['data']['scales'][s]:
            return int(self._data['data']['scales'][s]['resolution_z'])
        else:
            logger.warning('resolution_z not in dictionary')
            # return int(50)

    def set_resolutions(self, scale, res_x:int, res_y:int, res_z:int):
        self._data['data']['scales'][scale]['resolution_x'] = res_x
        self._data['data']['scales'][scale]['resolution_y'] = res_y
        self._data['data']['scales'][scale]['resolution_z'] = res_z


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
        if s == None: s = cfg.data.scale()
        return 'Scale %d' % self.scale_val(s=s)

    def scale_val(self, s=None) -> int:
        if s == None: s = cfg.data.scale()
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

    def n_layers(self) -> int:
        '''Returns # of imported images.
        #TODO Check this for off-by-one bug'''
        try:
            if self.is_mendenhall():
                return cfg.main_window.mendenhall.n_files()
            else:
                return len(self._data['data']['scales']['scale_1']['alignment_stack'])
        except:
            logger.warning('No Images Found - Returning 0')

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
        # logger.info('skipped (called By %s)' % inspect.stack()[1].function)
        # print('Before Defaults: s = %s, l = %s' % (str(s), str(l))) # Before Defaults: s = None, l = None
        if s == None: s = self.scale()
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
        if s == None: s = self.scale()
        indexes, names = [], []
        try:
            for i,layer in enumerate(self.alstack(s=s)):
                if layer['skipped'] == True:
                    indexes.append(i)
                    names.append(os.path.basename(layer['images']['base']['filename']))
            return list(zip(indexes, names))
        except:
            print_exception()
            logger.warning('Unable to To Return Skips List');
            return []

    def skips_by_name(self, s=None) -> list[str]:
        '''Returns the list of skipped images for a s'''
        if s == None: s = self.scale()
        lst = []
        try:
            for i in range(self.n_layers()):
                if self._data['data']['scales'][s]['alignment_stack'][i]['skipped'] == True:
                    f = os.path.basename(self._data['data']['scales'][s]['alignment_stack'][i][
                                             'images']['base']['filename'])
                    lst.append(f)
            return lst
        except:
            logger.warning('Unable to To Return Skips By Name List');
            return []

    def whitening(self) -> float:
        '''Returns the Whitening Factor for the Current Layer.'''
        return float(self._data['data']['scales'][self.scale()]['alignment_stack'][
                         self.layer()]['align_to_ref_method']['method_data']['whitening_factor'])

    def swim_window(self) -> float:
        '''Returns the SWIM Window for the Current Layer.'''
        return float(self._data['data']['scales'][self.scale()]['alignment_stack'][
                         self.layer()]['align_to_ref_method']['method_data']['win_scale_factor'])

    def has_bb(self, s=None) -> bool:
        '''Returns the Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None: s = self.scale()
        return bool(self._data['data']['scales'][s]['use_bounding_rect'])

    def bounding_rect(self, s=None):
        if s == None: s = self.scale()
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
        if s == None: s = self.scale()
        # logger.info('Called by %s, s=%s' % (inspect.stack()[1].function, s))
        try:
            return self._data['data']['scales'][s]['image_src_size']
        except:
            logger.info("No key 'image_src_size' found. Adding it now...")
            try:
                self.set_image_size(scale=s)
                return self._data['data']['scales'][s]['image_src_size']
            except:
                print_exception()
                logger.warning('Unable to return the image size (s=%s)' % s)
                return None

    def poly_order(self, s=None) -> int:
        '''Returns the Polynomial Order for the Current Scale.'''
        if s == None: s = self.scale()
        return int(self._data['data']['scales'][s]['poly_order'])

    def null_cafm(self, s=None) -> bool:
        '''Gets the Null Cafm Trends On/Off State for the Current Scale.'''
        if s == None: s = self.scale()
        return bool(self._data['data']['scales'][s]['null_cafm_trends'])

    def al_option(self, s=None) -> str:
        '''Gets the Alignment Option for the Current Scale.'''
        if s == None: s = self.scale()
        return self._data['data']['scales'][s]['method_data']['alignment_option']

    def path_ref(self, s=None, l=None) -> str:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['images']['ref']['filename']

    def path_base(self, s=None, l=None) -> str:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        # Todo -- Refactor!
        try:
            name = self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['filename']
            return name
        except:
            print_exception()

    def name_base(self, s=None, l=None) -> str:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        try:
            return os.path.basename(self._data['data']['scales'][s]['alignment_stack'][l]['images']['base']['filename'])
        except:
            return ''

    def name_ref(self, s=None, l=None) -> str:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        try:
            return os.path.basename(self._data['data']['scales'][s]['alignment_stack'][l]['images']['ref']['filename'])
        except:
            return ''

    def path_aligned(self, s=None, l=None) -> str:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        return os.path.join(self.dest(), s, 'img_aligned', self.name_base(l=l))

    def zarr_scale_paths(self):
        l = []
        for s in self.scales():
            # l.append(os.path.join(self._data['data']['destination_path'], s + '.zarr'))
            l.append(os.path.join(self._data['data']['destination_path'], 'img_src.zarr', s + str(get_scale_val(s))))
        return l

    def roles(self):
        l, s = self.layer(), self.scale()
        return self._data['data']['scales'][s]['alignment_stack'][l]['images'].keys()

    def set_destination(self, s):
        self._data['data']['destination_path'] = s

    def set_scale(self, x:str) -> None:
        '''Sets the Current Scale.'''
        self._data['data']['current_scale'] = x

    def set_layer(self, index:int) -> None:
        '''Sets Current Layer To Index.'''
        assert isinstance(index, int)
        logger.info(f'setting layer to {index}')
        self._data['data']['current_layer'] = index

    def set_skip(self, b: bool, s=None, l=None) -> None:
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['data']['scales'][s]['alignment_stack'][l]['skipped'] = b

    def set_whitening(self, f: float) -> None:
        '''Sets the Whitening Factor for the Current Layer.'''
        self._data['data']['scales'][self.scale()]['alignment_stack'][self.layer()][
            'align_to_ref_method']['method_data']['whitening_factor'] = f

    def set_swim_window(self, f: float) -> None:
        '''Sets the SWIM Window for the Current Layer.'''
        self._data['data']['scales'][self.scale()]['alignment_stack'][self.layer()][
            'align_to_ref_method']['method_data']['win_scale_factor'] = f

    def set_use_bounding_rect(self, b: bool, s=None) -> None:
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        if s == None:
            for s in self.scales():
                self._data['data']['scales'][s]['use_bounding_rect'] = bool(b)
        else:
            self._data['data']['scales'][s]['use_bounding_rect'] = bool(b)

    def set_bounding_rect(self, bounding_rect: list, s=None) -> None:
        if s == None: s = self.scale()
        self._data['data']['scales'][s]['bounding_rect'] = bounding_rect

    def set_calculate_bounding_rect(self, s=None):
        if s == None: s = self.scale()
        self.set_bounding_rect(ComputeBoundingRect(self.alstack(s=s)))
        return self.bounding_rect()

    def set_image_size(self, scale) -> None:
        self._data['data']['scales'][scale]['image_src_size'] = ImageSize(self.path_base(s=scale))
        logger.info(f'Scale Image Sizes Resolved, {self.scale_pretty(s=scale)}: {self.image_size(s=scale)}')

    def set_image_size_directly(self, size, s=None):
        if s == None: s = cfg.data.scale()
        logger.info(f"Setting Image Sizes Directly, {s}, ImageSize: {size}")
        self._data['data']['scales'][s]['image_src_size'] = size

    def set_poly_order(self, x: int) -> None:
        '''Sets the Polynomial Order for the Current Scale.'''
        self._data['data']['scales'][self.scale()]['poly_order'] = int(x)

    def set_use_poly_order(self, b: bool) -> None:
        '''Sets the Null Cafm Trends On/Off State for the Current Scale.'''
        self._data['data']['scales'][self.scale()]['null_cafm_trends'] = bool(b)

    # def make_absolute(file_path, proj_path):
    #     abs_path = os.path.join(os.path.split(proj_path)[0], file_path)
    #     return abs_path

    def set_al_dict(self, aldict, s=None):
        if s == None: s = self.scale()
        try:
            self._data['data']['scales'][s]['alignment_stack'] = aldict
        except:
            logger.warning('Unable to set alignment dict')

    def set_afm(self, afm: list, s=None, l=None) -> None:
        '''set afm as list of lists of floats'''
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        try:
            self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['cumulative_afm'] = afm
        except:
            print_exception()

    def set_cafm(self, cafm: list, s=None, l=None) -> None:
        '''set cafm as list of lists of floats'''
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        try:
            self._data['data']['scales'][s]['alignment_stack'][l][
                'align_to_ref_method']['method_results']['cumulative_afm'] = cafm
        except:
            print_exception()

    def selected_method(self, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        return self._data['data']['scales'][s]['alignment_stack'][l]['align_to_ref_method']['selected_method']

    def set_selected_method(self, method, s=None, l=None):
        if s == None: s = self.scale()
        if l == None: l = self.layer()
        self._data['data']['scales'][s]['alignment_stack'][l]['align_to_ref_method']['selected_method'] = method


    def set_destination_absolute(self, head):
        head = os.path.split(head)[0]
        self.set_destination(os.path.join(head, self.dest()))

    def set_paths_absolute(self, filename):
        logger.info(f'Setting Absolute File Paths - Destination: {filename}')
        # returns path to project file minus extension (should be the project directory)
        self.set_destination(os.path.splitext(filename)[0])
        logger.debug(f'Setting absolute project dest/head: {self.dest()}')
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

        Get aligned scales list. Check project data and aligned Zarr group presence.'''
        lst = []
        for s in self.scales():
            r = self._data['data']['scales'][s]['alignment_stack'][-1]['align_to_ref_method']['method_results']
            if r != {}:
                lst.append(s)
        for s in lst:
            if not is_arg_scale_aligned(s):
                lst.remove(s)
        return lst

    # def not_aligned_list(self) -> list[str]:
    #     '''Get not aligned scales list.'''
    #     lst = []
    #     for s in self.scales():
    #         if not is_arg_scale_aligned(s):
    #             lst.append(s)
    #     logger.debug('Not Aligned Scales List: %s ' % str(lst))
    #     return lst

    def not_aligned_list(self):
        return set(self.scales()) - set(self.scalesAligned)

    def coarsest_scale_key(self) -> str:
        '''Return the coarsest s key. '''
        return self.scales()[-1]

    def next_coarsest_scale_key(self) -> str:
        if self.n_scales() == 1:
            return self.scale()
        scales_dict = self._data['data']['scales']
        cur_scale_key = self.scale()
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
        '''Checks if the current s is able to be aligned'''
        try:
            if cfg.data.dest() in ('', None):
                logger.debug("is_alignable returning False because: "
                             "cfg.data.dest() in ('', None) is True")
                return False

            if not are_images_imported():
                logger.debug("is_alignable returning False because: "
                             "not are_images_imported() is True")
                return False
            scales_list = self.scales()
            cur_scale_key = self.scale()
            coarsest_scale = scales_list[-1]
            if cur_scale_key == coarsest_scale:
                logger.debug("is_alignable returning True because: "
                             "cur_scale_key == coarsest_scale) is True")
                return True
            cur_scale_index = scales_list.index(cur_scale_key)
            next_coarsest_scale_key = scales_list[cur_scale_index + 1]
            if not is_arg_scale_aligned(next_coarsest_scale_key):
                logger.debug("is_alignable returning False because: "
                             "not is_arg_scale_aligned(next_coarsest_scale_key) is True")
                return False
            else:
                logger.debug('Returning True')
                return True
        except:
            print_exception()

    def clear_all_skips(self):
        logger.info('Clearing all skips...')
        for scale in self.scales():
            scale_key = str(scale)
            for layer in self._data['data']['scales'][scale_key]['alignment_stack']:
                layer['skipped'] = False

    def append_layer(self, scale_key):
        self._data['data']['scales'][scale_key]['alignment_stack'].append(
            {
                "align_to_ref_method": {
                    "method_data": {},
                    "method_options": {},
                    "selected_method": "Auto Swim Align",
                    "method_results": {}
                },
                "images": {},
                "skipped": False
            })
        pass

    def append_image(self, image_file_name, role_name='base'):
        logger.debug("Adding Image %s to Role '%s'" % (image_file_name, role_name))
        scale = cfg.data.scale()
        used_for_this_role = [role_name in l['images'].keys() for l in self.alstack(s=scale)]
        if False in used_for_this_role:
            layer_index = used_for_this_role.index(False)
        else:
            cfg.data.append_layer(scale_key=scale)
            layer_index = self.n_layers() - 1
        self.add_img(
            scale_key=scale,
            layer_index=layer_index,
            role=role_name,
            filename=image_file_name
        )

    def append_empty(self, role_name):
        logger.debug('MainWindow.append_empty:')
        scale = cfg.data.scale()
        used_for_this_role = [role_name in l['images'].keys() for l in self.alstack(s=scale)]
        layer_index = -1
        if False in used_for_this_role:
            layer_index = used_for_this_role.index(False)
        else:
            cfg.data.append_layer(scale_key=scale)
            layer_index_for_new_role = len(cfg.data['data']['scales'][scale]['alignment_stack']) - 1
        cfg.data.add_img(
            scale_key=scale,
            layer_index=layer_index,
            role=role_name,
            filename=None
        )

    def add_img(self, scale_key, layer_index, role, filename=''):
        logger.info('Adding Image scale_key=%s, layer_index=%s, role=%s, filename=%s' % (scale_key, str(layer_index), role, filename))
        self._data['data']['scales'][scale_key]['alignment_stack'][layer_index]['images'][role] = \
            {
                "filename": filename,
                "metadata": {
                    "annotations": [],
                    "match_points": []
                }
            }

    def update_datamodel(self, updated_model):
        '''This function is called by align_layers and regenerate_aligned. It is called when
        'run_json_project' returns with need_to_write_json=false'''
        logger.info('Updating Data Model...')
        # Load the alignment stack after the alignment has completed
        aln_image_stack = []
        scale = self.scale()
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
        if len(cfg.data.skips_list()) > 0:
            return True
        else:
            return False

    def set_scales_from_string(self, scale_string: str):
        '''This is not pretty. Needs to be refactored ASAP.
        Two callers: 'new_project', 'prepare_generate_scales_worker'
        '''
        cur_scales = [str(v) for v in sorted([get_scale_val(s) for s in self._data['data']['scales'].keys()])]
        scale_str = scale_string.strip()
        if len(scale_str) > 0:
            input_scales = []
            try:
                input_scales = [str(v) for v in sorted([get_scale_val(s) for s in scale_str.strip().split(' ')])]
            except:
                logger.info("Bad input: (" + str(scale_str) + "), Scales not changed")
                input_scales = []

            if not (input_scales == cur_scales):
                # The scales have changed!!
                # self.define_scales_menu (input_scales)
                cur_scale_keys = [get_scale_key(v) for v in cur_scales]
                input_scale_keys = [get_scale_key(v) for v in input_scales]

                # Remove any scales not in the new list (except always leave 1)
                scales_to_remove = []
                for scale_key in self.scales():
                    if not (scale_key in input_scale_keys):
                        if get_scale_val(scale_key) != 1:
                            scales_to_remove.append(scale_key)
                for scale_key in scales_to_remove:
                    self._data['data']['scales'].pop(scale_key)

                # Add any scales not in the new list
                scales_to_add = []
                for scale_key in input_scale_keys:
                    if not (scale_key in self.scales()):
                        scales_to_add.append(scale_key)
                for scale_key in scales_to_add:
                    new_stack = []
                    scale_1_stack = self._data['data']['scales'][get_scale_key(1)]['alignment_stack']
                    for l in scale_1_stack:
                        new_layer = deepcopy(l)
                        new_stack.append(new_layer)
                    self._data['data']['scales'][scale_key] = {'alignment_stack': new_stack,
                                                               'method_data': {
                                                                   'alignment_option': 'init_affine'}}
        else:
            logger.info("No input: Scales not changed")

    def ensure_proper_data_structure(self):
        '''Ensure Proper Data Structure (that the previewmodel is usable)...'''
        logger.debug('Ensuring called by %s' % inspect.stack()[1].function)
        '''  '''
        scales_dict = self._data['data']['scales']
        coarsest = list(scales_dict.keys())[-1]
        for scale_key in scales_dict.keys():
            scale = scales_dict[scale_key]
            scale.setdefault('use_bounding_rect', cfg.DEFAULT_BOUNDING_BOX)
            scale.setdefault('null_cafm_trends', cfg.DEFAULT_NULL_BIAS)
            scale.setdefault('poly_order', cfg.DEFAULT_POLY_ORDER)
            for layer_index in range(len(scale['alignment_stack'])):
                layer = scale['alignment_stack'][layer_index]
                layer.setdefault('align_to_ref_method', {})
                layer['align_to_ref_method'].setdefault('method_data', {})
                layer['align_to_ref_method']['method_data'].setdefault('win_scale_factor', cfg.DEFAULT_SWIM_WINDOW)
                layer['align_to_ref_method']['method_data'].setdefault('whitening_factor', cfg.DEFAULT_WHITENING)
                if scale_key == coarsest:
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
                else:
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'

    def link_all_stacks(self):
        '''Called by the functions 'skip_changed_callback' and 'import_images'  '''
        # logger.info('link_all_stacks (called by %s):' % inspect.stack()[1].function)
        self.ensure_proper_data_structure()  # 0712 #0802 #original
        for scale_key in self.scales():
            skip_list = []
            for layer_index in range(len(self._data['data']['scales'][scale_key]['alignment_stack'])):
                try:
                    if self._data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skipped'] == True:
                        skip_list.append(layer_index)
                except:
                    print_exception()
                base_layer = self._data['data']['scales'][scale_key]['alignment_stack'][layer_index]
                if layer_index == 0:
                    if 'ref' not in base_layer['images'].keys():
                        self.add_img(scale_key=scale_key, layer_index=layer_index, role='ref', filename='')
                elif layer_index in skip_list:
                    # No ref for skipped l
                    if 'ref' not in base_layer['images'].keys():
                        self.add_img(scale_key=scale_key, layer_index=layer_index, role='ref', filename='')

                else:
                    # Find nearest previous non-skipped l
                    j = layer_index - 1
                    while (j in skip_list) and (j >= 0):
                        j -= 1

                    # Use the nearest previous non-skipped l as ref for this l
                    if (j not in skip_list) and (j >= 0):
                        ref_layer = self._data['data']['scales'][scale_key]['alignment_stack'][j]
                        ref_fn = ''
                        if 'base' in ref_layer['images'].keys():
                            ref_fn = ref_layer['images']['base']['filename']
                        if 'ref' not in base_layer['images'].keys():
                            self.add_img(scale_key=scale_key, layer_index=layer_index, role='ref', filename=ref_fn)
                        else:
                            base_layer['images']['ref']['filename'] = ref_fn

    def upgrade_data_model(self):
        # Upgrade the "Data Model"
        if self._data['version'] != self._current_version:
            logger.critical('Upgrading Data Model...')

            # Begin the upgrade process:

            if self._data['version'] <= 0.26:
                logger.info("Upgrading data previewmodel from " + str(self._data['version']) + " to " + str(0.27))
                # Need to modify the data previewmodel from 0.26 or lower up to 0.27
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
                        # Ensure that there's some method data
                        scale['method_data'] = {}
                    # Finally set the value
                    scale['method_data']["alignment_option"] = scale_option
                # Now the data previewmodel is at 0.27, so give it the appropriate version
                self._data['version'] = 0.27

            if self._data['version'] == 0.27:
                print("\n\nUpgrading data previewmodel from " + str(self._data['version']) + " to " + str(0.28))
                # Need to modify the data previewmodel from 0.27 up to 0.28
                # The "alignment_option" had been left in the method_data at each l
                # This new version removes that option from the l method data
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
                # Now the data previewmodel is at 0.28, so give it the appropriate version
                self._data['version'] = 0.28

            if self._data['version'] == 0.28:
                print("\n\nUpgrading data previewmodel from " + str(self._data['version']) + " to " + str(0.29))
                # Need to modify the data previewmodel from 0.28 up to 0.29
                # The "use_c_version" was added to the "user_settings" dictionary
                self._data['user_settings']['use_c_version'] = True
                # Now the data previewmodel is at 0.29, so give it the appropriate version
                self._data['version'] = 0.29

            if self._data['version'] == 0.29:
                print("\n\nUpgrading data previewmodel from " + str(self._data['version']) + " to " + str(0.30))
                # Need to modify the data previewmodel from 0.29 up to 0.30
                # The "poly_order" was added to the "scales" dictionary
                for scale_key in self.scales():
                    scale = self._data['data']['scales'][scale_key]
                    scale['poly_order'] = 4
                # Now the data previewmodel is at 0.30, so give it the appropriate version
                self._data['version'] = 0.30

            if self._data['version'] == 0.30:
                print("\n\nUpgrading data previewmodel from " + str(self._data['version']) + " to " + str(0.31))
                # Need to modify the data previewmodel from 0.30 up to 0.31
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
                # Now the data previewmodel is at 0.31, so give it the appropriate version
                self._data['version'] = 0.31
            if self._data['version'] == 0.31:
                print("\n\nUpgrading data previewmodel from " + str(self._data['version']) + " to " + str(0.32))
                # Need to modify the data previewmodel from 0.31 up to 0.32
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
                # Now the data previewmodel is at 0.32, so give it the appropriate version
                # data_model ['version'] = 0.32

            # Make the final test
            if self._data['version'] != self._current_version:
                # The data previewmodel could not be upgraded, so return a string with the error
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
