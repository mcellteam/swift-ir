"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""
import os
import json
import logging
from copy import deepcopy

import alignEM.config as cfg
from alignEM.ui.defaults_form import DefaultsForm

__all__ = ['DataModel']

logger = logging.getLogger(__name__)

class DataModel:
    """ Encapsulate data model dictionary and wrap with methods for convenience """

    def __init__(self, data=None):

        self._current_version = 0.31


        if data != None:
            self._project_data = data
        else:
            self._project_data = \
                {
                    "version": 0.31,
                    "method": "None",
                    "user_settings": {
                        "max_image_file_size": 100000000,
                        "use_c_version": True
                    },
                    "data": {
                        "source_path": "",
                        "destination_path": "",
                        "current_layer": 0,
                        "current_scale": "scale_1",
                        "panel_roles": [
                            "ref",
                            "base",
                            "aligned"
                        ],
                        "scales": {
                            "scale_1": {
                                "method_data": {
                                    "alignment_option": "init_affine"
                                },
                                "null_cafm_trends": False,
                                "use_bounding_rect": True,
                                "alignment_stack": []
                            }
                        }
                    }
                }
        if self._project_data['version'] != self._current_version:
            self.upgrade_data_model()

    def __setitem__(self, key, item):
        self._project_data[key] = item

    def __getitem__(self, key):
        return self._project_data[key]

    # def __str__(self):
    #     return json.dumps(self._project_data)

    def to_json(self):
        return json.dumps(self._project_data)

    def to_dict(self):
        return self._project_data

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

    def settings(self):
        cfg.defaults_form.show()

    def destination(self):
        return self._project_data['data']['destination_path']

    def name(self):
        return self._project_data['data']['destination_path']

    def append_layer(self, scale_key):
        self._project_data['data']['scales'][scale_key]['alignment_stack'].append(
            {
                "align_to_ref_method": {
                    "method_data": {},
                    # "method_options": [
                    #     "None"
                    # ],
                    "method_options": {},
                    "selected_method": "None",
                    "method_results": {}
                },
                "images": {},
                "skip": False
            })
        pass


    def add_img(self, scale_key, layer_index, role, filename=''):
        self._project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]['images'][role] = \
            {
                "filename": filename,
                "metadata": {
                    "annotations": [],
                    "match_points": []
                }
            }


    def ensure_proper_data_structure(self):
        '''Ensure that the data model is usable.'''
        logger.info('ensure_proper_data_structure >>>>')
        '''  '''
        scales_dict = self._project_data['data']['scales']
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
        logger.info("<<<< ensure_proper_data_structure")

    def link_all_stacks(self):
        '''Called by the functions 'skip_changed_callback' and 'import_images'  '''
        logger.debug('link_all_stacks >>>>')
        self.ensure_proper_data_structure()  # 0712 #0802 #original
        for scale_key in self._project_data['data']['scales'].keys():
            skip_list = []
            for layer_index in range(len(self._project_data['data']['scales'][scale_key]['alignment_stack'])):
                if self._project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skip'] == True:
                    skip_list.append(layer_index)
                base_layer = self._project_data['data']['scales'][scale_key]['alignment_stack'][layer_index]
                if layer_index == 0:
                    if 'ref' not in base_layer['images'].keys():
                        self.add_img(scale_key=scale_key, layer_index=layer_index, role='ref', filename='')
                elif layer_index in skip_list:
                    # No ref for skipped layer
                    if 'ref' not in base_layer['images'].keys():
                        self.add_img(scale_key=scale_key, layer_index=layer_index, role='ref', filename='')

                else:
                    # Find nearest previous non-skipped layer
                    j = layer_index - 1
                    while (j in skip_list) and (j >= 0):
                        j -= 1

                    # Use the nearest previous non-skipped layer as ref for this layer
                    if (j not in skip_list) and (j >= 0):
                        ref_layer = self._project_data['data']['scales'][scale_key]['alignment_stack'][j]
                        ref_fn = ''
                        if 'base' in ref_layer['images'].keys():
                            ref_fn = ref_layer['images']['base']['filename']
                        if 'ref' not in base_layer['images'].keys():
                            self.add_img(scale_key=scale_key, layer_index=layer_index, role='ref', filename=ref_fn)
                        else:
                            base_layer['images']['ref']['filename'] = ref_fn

        # cfg.main_window.update_win_self()
        # cfg.main_window.center_all_images()  # 0702 necessary call
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        logger.debug('<<<< link_all_stacks')

    def upgrade_data_model(self, data_model):
        # Upgrade the "Data Model"
        if data_model['version'] != self._current_version:

            # Begin the upgrade process:

            if data_model['version'] <= 0.26:
                print("\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.27))
                # Need to modify the data model from 0.26 or lower up to 0.27
                # The "alignment_option" had been in the method_data at each layer
                # This new version defines it only at the scale level
                # So loop through each scale and move the alignment_option from the layer to the scale
                for scale_key in data_model['data']['scales'].keys():
                    scale = data_model['data']['scales'][scale_key]
                    stack = scale['alignment_stack']
                    current_alignment_options = []
                    for layer in stack:
                        if "align_to_ref_method" in layer:
                            align_method = layer['align_to_ref_method']
                            if 'method_data' in align_method:
                                if 'alignment_option' in align_method['method_data']:
                                    current_alignment_options.append(align_method['method_data']['alignment_option'])
                    # The current_alignment_options list now holds all of the options for this scale (if any)
                    # Start by setting the default for the scale option to "init_affine" if none are found
                    scale_option = "init_affine"
                    # If any options were found in this scale, search through them for most common
                    if len(current_alignment_options) > 0:
                        # They should all be the same at this scale, so set to the first
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
                # Now the data model is at 0.27, so give it the appropriate version
                data_model['version'] = 0.27

            if data_model['version'] == 0.27:
                print("\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.28))
                # Need to modify the data model from 0.27 up to 0.28
                # The "alignment_option" had been left in the method_data at each layer
                # This new version removes that option from the layer method data
                # So loop through each scale and remove the alignment_option from the layer
                for scale_key in data_model['data']['scales'].keys():
                    scale = data_model['data']['scales'][scale_key]
                    stack = scale['alignment_stack']
                    current_alignment_options = []
                    for layer in stack:
                        if "align_to_ref_method" in layer:
                            align_method = layer['align_to_ref_method']
                            if 'method_data' in align_method:
                                if 'alignment_option' in align_method['method_data']:
                                    align_method['method_data'].pop('alignment_option')
                # Now the data model is at 0.28, so give it the appropriate version
                data_model['version'] = 0.28

            if data_model['version'] == 0.28:
                print("\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.29))
                # Need to modify the data model from 0.28 up to 0.29
                # The "use_c_version" was added to the "user_settings" dictionary
                data_model['user_settings']['use_c_version'] = True
                # Now the data model is at 0.29, so give it the appropriate version
                data_model['version'] = 0.29

            if data_model['version'] == 0.29:
                print("\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.30))
                # Need to modify the data model from 0.29 up to 0.30
                # The "poly_order" was added to the "scales" dictionary
                for scale_key in data_model['data']['scales'].keys():
                    scale = data_model['data']['scales'][scale_key]
                    scale['poly_order'] = 4
                # Now the data model is at 0.30, so give it the appropriate version
                data_model['version'] = 0.30

            if data_model['version'] == 0.30:
                print("\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.31))
                # Need to modify the data model from 0.30 up to 0.31
                # The "skipped(1)" annotation is currently unused (now hard-coded in alignem.py)
                # Remove alll "skipped(1)" annotations since they can not otherwise be removed
                for scale_key in data_model['data']['scales'].keys():
                    scale = data_model['data']['scales'][scale_key]
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
                # Now the data model is at 0.31, so give it the appropriate version
                data_model['version'] = 0.31
            if data_model['version'] == 0.31:
                print("\n\nUpgrading data model from " + str(data_model['version']) + " to " + str(0.32))
                # Need to modify the data model from 0.31 up to 0.32
                #   1) change name of method_results key "affine_matrix" to "afm"
                #   2) change name of method_results key "cumulative_afm" to "c_afm"
                #   3) add new method_results key, "aim" and compute/store this value
                #   4) add new method_results key, "c_aim" and compute/store this value
                #   5) add new method_results key, "reconstruct_x_coeff" and compute/store this value
                #   6) add new method_results key, "reconstruct_y_coeff" and compute/store this value
                #   7) add new scale key, "bounding_rect_x" and compute/store this value
                #   8) add new scale key, "bounding_rect_y" and compute/store this value
                # Note, aim and c_aim are the inverse of afm and c_afm
                # Note, c_afm and c_aim are the now the cumulative matrices not including
                #       the bounding rect.
                # Note, reconstruct_x_coeff and _y_coeff are the coefficients of the
                #       dim 3 polynomial basis transforms used by RECONSTRUCT.
                #       These coefficients do not include the bounding rect terms.
                #

                # FIXME: leave this commented out until we have finished 1-8 above
                # Now the data model is at 0.32, so give it the appropriate version
                # data_model ['version'] = 0.32

            # Make the final test
            if data_model['version'] != self._current_version:
                # The data model could not be upgraded, so return a string with the error
                data_model = 'Version mismatch. Expected "' + str(
                    self._current_version) + '" but found ' + str(
                    data_model['version'])

        return data_model

    # def update_init_rot(self):
    #     image_scales_to_run = [self.get_scale_val(s) for s in sorted(cfg.project_data['data']['scales'].keys())]
    #     for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #         scale_key = self.get_scale_key(scale)
    #         for i, layer in enumerate(cfg.project_data['data']['scales'][scale_key]['alignment_stack']):
    #             layer['align_to_ref_method']['method_options'] = {'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION}
    #     logger.critical('cfg.DEFAULT_INITIAL_ROTATION = %f' % cfg.DEFAULT_INITIAL_ROTATION)
    #
    # def update_init_scale(self):
    #     image_scales_to_run = [self.get_scale_val(s) for s in sorted(cfg.project_data['data']['scales'].keys())]
    #     for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #         scale_key = self.get_scale_key(scale)
    #         for i, layer in enumerate(cfg.project_data['data']['scales'][scale_key]['alignment_stack']):
    #             layer['align_to_ref_method']['method_options'] = {'initial_scale': cfg.DEFAULT_INITIAL_SCALE}
    #     logger.critical('cfg.DEFAULT_INITIAL_SCALE = %f' % cfg.DEFAULT_INITIAL_SCALE)

    def get_scale_key(self, scale_val):
        # Create a key like "scale_#" from either an integer or a string
        s = str(scale_val)
        while s.startswith('scale_'):
            s = s[len('scale_'):]
        return 'scale_' + s

    def get_scale_val(self, scale_of_any_type):
        '''Converts scale key to integer (i.e. 'scale_1' as string -> 1 as int)
        This should return an integer value from any reasonable input (string or int)'''
        scale = scale_of_any_type
        if type(scale) == type(1):
            # It's already an integer, so return it
            return scale
        else:  # elif type(scale) in [ str, unicode ]:
            # It's a string, so remove any optional "scale_" prefix(es) and return as int
            while scale.startswith('scale_'):
                scale = scale[len('scale_'):]
            return int(scale)

    def clear_method_results(self, scale_key, start_layer=0):
        for layer in self._project_data['data']['scales'][scale_key]['alignment_stack'][start_layer:]:
            layer['align_to_ref_method']['method_results'] = {}


# # layer_dict as defined in run_project_json.py:
# layer_dict = {
#     "images": {
#         "base": {
#             "metadata": {
#                 "match_points": match_points[0]
#             }
#         },
#         "ref": {
#             "metadata": {
#                 "match_points": match_points[1]
#             }
#         }
#     },
#     "align_to_ref_method": {
#         "selected_method": "Match Point Align",
#         "method_options": [
#             "Auto Swim Align",
#             "Match Point Align"
#         ],
#         "method_data": {},
#         "method_results": {}
#     }
# }

if __name__ == '__main__':
    data = DataModel()
    print('Data Model Version: ' + str(data['version']))
    print(data)

