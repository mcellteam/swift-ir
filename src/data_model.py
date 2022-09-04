"""AlignEm - Alignment Framework for multiple images

AlignEm is intended to provide a tool for supporting image alignment
using any number of technologies.
"""
import os
import json
import inspect
import logging
from copy import deepcopy
import src.config as cfg
from src.helpers import print_exception, natural_sort, are_images_imported, is_arg_scale_aligned, get_scale_key, \
    get_scale_val

__all__ = ['DataModel']

logger = logging.getLogger(__name__)


class DataModel:
    """ Encapsulate data model dictionary and wrap with methods for convenience """

    def __init__(self, data=None, name=''):

        self._current_version = 0.31

        if data != None:
            self._data = data
        else:
            self._data = \
                {
                    "version": 0.31,
                    "method": "None",
                    "user_settings": {
                        "max_image_file_size": 100000000,
                        "use_c_version": True
                    },
                    "data": {
                        "source_path": "",
                        "destination_path": name,
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
        if self._data['version'] != self._current_version:
            self.upgrade_data_model()

    def __setitem__(self, key, item):
        self._data[key] = item

    def __getitem__(self, key):
        return self._data[key]

    # def __str__(self):
    #     return json.dumps(self._data)

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

    def to_json(self):
        return json.dumps(self._data)

    def to_dict(self):
        return self._data

    def set_destination(self, s):
        self._data['data']['destination_path'] = s

    def destination(self):
        return self._data['data']['destination_path']

    def get_scale(self) -> str:
        '''Returns the Current Scale as a String.'''
        return self._data['data']['current_scale']

    def get_layer(self) -> int:
        '''Returns the Current Layer as an Integer.'''
        return self._data['data']['current_layer']

    def get_skip(self) -> bool:
        '''Returns the Bounding Rectangle On/Off State for the Current Scale.'''
        return bool(self._data['data']['scales'][self.get_scale()]['alignment_stack'][self.get_layer()]['skip'])

    def get_whitening(self) -> float:
        '''Returns the Whitening Factor for the Current Layer.'''
        return float(self._data['data']['scales'][self.get_scale()]['alignment_stack'][
                         self.get_layer()]['align_to_ref_method']['method_data']['whitening_factor'])

    def get_swim_window(self) -> float:
        '''Returns the SWIM Window for the Current Layer.'''
        return float(self._data['data']['scales'][self.get_scale()]['alignment_stack'][
                         self.get_layer()]['align_to_ref_method']['method_data']['win_scale_factor'])

    def get_bounding_rect(self) -> bool:
        '''Returns the Bounding Rectangle On/Off State for the Current Scale.'''
        return bool(self._data['data']['scales'][self.get_scale()]['use_bounding_rect'])

    def get_poly_order(self) -> int:
        '''Returns the Polynomial Order for the Current Scale.'''
        return int(self._data['data']['scales'][self.get_scale()]['poly_order'])

    def get_null_cafm(self) -> bool:
        '''Gets the Null Cafm Trends On/Off State for the Current Scale.'''
        return bool(self._data['data']['scales'][self.get_scale()]['null_cafm_trends'])


    def set_scale(self, x:str) -> None:
        '''Sets the Current Scale.'''
        self._data['data']['current_scale'] = x

    def set_layer(self, x:int) -> None:
        '''Sets the Current Layer as Integer.'''
        self._data['data']['current_layer'] = x

    def set_skip(self, b:bool) -> None:
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['data']['scales'][self.get_scale()]['alignment_stack'][self.get_layer()]['skip'] = b

    def set_whitening(self, f:float) -> None:
        '''Sets the Whitening Factor for the Current Layer.'''
        self._data['data']['scales'][self.get_scale()]['alignment_stack'][self.get_layer()][
            'align_to_ref_method']['method_data']['whitening_factor'] = f

    def set_swim_window(self, f:float) -> None:
        '''Sets the SWIM Window for the Current Layer.'''
        self._data['data']['scales'][self.get_scale()]['alignment_stack'][self.get_layer()][
            'align_to_ref_method']['method_data']['win_scale_factor'] = f

    def set_bounding_rect(self, b:bool) -> None:
        '''Sets the Bounding Rectangle On/Off State for the Current Scale.'''
        self._data['data']['scales'][self.get_scale()]['use_bounding_rect'] = b

    def set_poly_order(self, x:int) -> None:
        '''Sets the Polynomial Order for the Current Scale.'''
        self._data['data']['scales'][self.get_scale()]['poly_order'] = x

    def set_null_cafm(self, b:bool) -> None:
        '''Sets the Null Cafm Trends On/Off State for the Current Scale.'''
        self._data['data']['scales'][self.get_scale()]['null_cafm_trends'] = b


    '''
        @Slot()
    def get_whitening_input(self) -> float:
        return float(self.whitening_input.text())
    
    @Slot()
    def get_swim_input(self) -> float:
        return float(self.swim_input.text())
    
    @Slot()
    def get_bounding_state(self):
        return self.toggle_bounding_rect.isChecked()
    
    @Slot()
    def get_null_bias_value(self) -> str:
        return str(self.null_bias_combobox.currentText())
    '''


    def get_snr(self) -> str:
        '''TODO This probably shouldn't return a string'''
        if not self._data['data']['current_scale']:
            logger.warning("Can't Get SNR Because Scale is Not Set")
            return ''
        try:
            s = self._data['data']['current_scale']
            l = self._data['data']['current_layer']
            if len(self._data['data']['scales']) > 0:
                scale = self._data['data']['scales'][s]
                if len(scale['alignment_stack']) > 0:
                    layer = scale['alignment_stack'][l]
                    if 'align_to_ref_method' in layer:
                        if 'method_results' in layer['align_to_ref_method']:
                            method_results = layer['align_to_ref_method']['method_results']
                            if 'snr_report' in method_results:
                                if method_results['snr_report'] != None:
                                    curr_snr = method_results['snr_report']
                                    logger.debug("  returning the current snr: %s" % str(curr_snr))
                                    return str(curr_snr)
        except:
            logger.warning('An Exception Was Raised Trying To Get SNR of The Current Layer')

    def snr_list(self):
        snr_list = []
        for layer in self._data['data']['scales'][self._data.cur_scale()]['alignment_stack']:
            try:
                snr_vals = layer['align_to_ref_method']['method_results']['snr']
                mean_snr = sum(snr_vals) / len(snr_vals)
                snr_list.append(mean_snr)
            except:
                pass
        return snr_list

    def clear_all_skips(self):
        logger.info('Clearing all skips...')
        image_scale_keys = [s for s in sorted(self._data['data']['scales'].keys())]
        for scale in image_scale_keys:
            scale_key = str(scale)
            for layer in self._data['data']['scales'][scale_key]['alignment_stack']:
                layer['skip'] = False

    # def get_layer(self) -> int:
    #     '''Returns the Current Layer'''
    #     return self._data['data']['current_layer']

    def get_n_images(self) -> int:
        '''Returns # of imported images.
        #TODO Check this for off-by-one bug'''
        try:
            n_imgs = len(self._data['data']['scales']['scale_1']['alignment_stack'])
            return n_imgs
        except:
            logger.warning('No Images Found - Returning 0')
            return 0  # 0711

    def get_skips(self) -> list[int]:
        '''Returns the list of skipped images at the current scale'''
        l = []
        try:
            scale = self.get_scale()
            for i in range(self.get_n_images()):
                if self._data['data']['scales'][scale]['alignment_stack'][i]['skip'] == True:
                    l.append(i)
        except:
            logger.warning('Unable to To Get Skips');
            return []
        else:
            return l

    def get_n_scales(self) -> int:
        '''Returns the number of scales in scale pyramid'''
        try:
            n_scales = len(self._data['data']['scales'].keys())
            return n_scales
        except:
            logger.warning('No Scales Found - Returning 0')
            return 0

    def get_scales(self) -> list[str]:
        '''Get scales list.
        Faster than O(n*m) performance.
        Preserves order of scales.'''
        l = natural_sort([key for key in self._data['data']['scales'].keys()])
        # logger.critical('Returning %s ' % str(l))
        return l

    def get_scale_vals(self) -> list[int]:
        return [int(v) for v in sorted([get_scale_val(s) for s in self._data['data']['scales'].keys()])]

    def get_aligned_scales_list(self) -> list[str]:
        '''Get aligned scales list.'''
        l = natural_sort([key for key in self._data['data']['scales'].keys()])
        # logger.critical('Returning %s ' % str(l))
        return l

    def get_not_aligned_scales_list(self) -> list[str]:
        '''Get not aligned scales list.'''
        l = natural_sort([key for key in self.get_scales() if key not in set(self.get_aligned_scales_list())])
        # logger.critical('Returning %s ' % str(l))
        return l

    def get_coarsest_scale_key(self) -> str:
        '''Return the coarsest scale key. '''
        key = natural_sort(list(self._data['data']['scales'].keys()))[-1]
        return key

    def get_next_coarsest_scale_key(self) -> str:
        if self.get_n_scales() == 1:
            return self.get_scale()
        scales_dict = self._data['data']['scales']
        cur_scale_key = self._data.cur_scale()
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
        answer = True
        if not are_images_imported():
            # logger.info('Returning False, images not imported')
            return False
        scales_list = self.get_scales()
        cur_scale_key = self.get_scale()
        coarsest_scale = scales_list[-1]
        if cur_scale_key == coarsest_scale:
            # logger.info('Returning True, current scale is the coarsest scale')
            return True
        cur_scale_index = scales_list.index(cur_scale_key)
        next_coarsest_scale_key = scales_list[cur_scale_index + 1]
        # logger.info('cur_scale_index = %d' % cur_scale_index)
        # logger.info('next_coarsest_scale_key = %s' % next_coarsest_scale_key)
        # logger.info('  index = %d' % (cur_scale_index + 1))
        if is_arg_scale_aligned(next_coarsest_scale_key):
            logger.info('Returning True')
            return True
        else:
            logger.info('Returning False')
            return False


    def al_stack(self) -> dict:
        al_stack = self._data['data']['scales'][self.get_scale()]['alignment_stack']
        return al_stack

    def append_layer(self, scale_key):
        self._data['data']['scales'][scale_key]['alignment_stack'].append(
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
        scale = self.get_scale()
        for layer in self.al_stack():
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

    def set_defaults(self) -> None:
        '''Force data defaults.'''
        logger.info('set_defaults:')
        scales_dict = self._data['data']['scales']
        coarsest_scale = list(scales_dict.keys())[-1]
        for scale_key in scales_dict.keys():
            scale = scales_dict[scale_key]
            scale['use_bounding_rect'] = cfg.DEFAULT_BOUNDING_BOX
            scale['null_cafm_trends'] = cfg.DEFAULT_NULL_BIAS
            scale['poly_order'] = cfg.DEFAULT_POLY_ORDER
            if scale_key == coarsest_scale:
                self._data['data']['scales'][scale_key]['method_data']['alignment_option'] = 'init_affine'
            else:
                self._data['data']['scales'][scale_key]['method_data']['alignment_option'] = 'refine_affine'
            for layer_index in range(len(scale['alignment_stack'])):
                layer = scale['alignment_stack'][layer_index]
                layer['align_to_ref_method']['method_data']['win_scale_factor'] = cfg.DEFAULT_SWIM_WINDOW
                layer['align_to_ref_method']['method_data']['whitening_factor'] = cfg.DEFAULT_WHITENING
                if scale_key == coarsest_scale:
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'init_affine'
                else:
                    layer['align_to_ref_method']['method_data']['alignment_option'] = 'refine_affine'

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
                for scale_key in self._data['data']['scales'].keys():
                    if not (scale_key in input_scale_keys):
                        if get_scale_val(scale_key) != 1:
                            scales_to_remove.append(scale_key)
                for scale_key in scales_to_remove:
                    self._data['data']['scales'].pop(scale_key)

                # Add any scales not in the new list
                scales_to_add = []
                for scale_key in input_scale_keys:
                    if not (scale_key in self._data['data']['scales'].keys()):
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
        '''Ensure that the data model is usable.'''
        logger.info('ensure_proper_data_structure (Called By %s)' % inspect.stack()[1].function)
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
        logger.info("<<<< ensure_proper_data_structure")

    def link_all_stacks(self):
        '''Called by the functions 'skip_changed_callback' and 'import_images'  '''
        logger.info('link_all_stacks:')
        self.ensure_proper_data_structure()  # 0712 #0802 #original
        for scale_key in self._data['data']['scales'].keys():
            skip_list = []
            for layer_index in range(len(self._data['data']['scales'][scale_key]['alignment_stack'])):
                if self._data['data']['scales'][scale_key]['alignment_stack'][layer_index]['skip'] == True:
                    skip_list.append(layer_index)
                base_layer = self._data['data']['scales'][scale_key]['alignment_stack'][layer_index]
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

            # Begin the upgrade process:

            if self._data['version'] <= 0.26:
                print("\n\nUpgrading data model from " + str(self._data['version']) + " to " + str(0.27))
                # Need to modify the data model from 0.26 or lower up to 0.27
                # The "alignment_option" had been in the method_data at each layer
                # This new version defines it only at the scale level
                # So loop through each scale and move the alignment_option from the layer to the scale
                for scale_key in self._data['data']['scales'].keys():
                    scale = self._data['data']['scales'][scale_key]
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
                self._data['version'] = 0.27

            if self._data['version'] == 0.27:
                print("\n\nUpgrading data model from " + str(self._data['version']) + " to " + str(0.28))
                # Need to modify the data model from 0.27 up to 0.28
                # The "alignment_option" had been left in the method_data at each layer
                # This new version removes that option from the layer method data
                # So loop through each scale and remove the alignment_option from the layer
                for scale_key in self._data['data']['scales'].keys():
                    scale = self._data['data']['scales'][scale_key]
                    stack = scale['alignment_stack']
                    current_alignment_options = []
                    for layer in stack:
                        if "align_to_ref_method" in layer:
                            align_method = layer['align_to_ref_method']
                            if 'method_data' in align_method:
                                if 'alignment_option' in align_method['method_data']:
                                    align_method['method_data'].pop('alignment_option')
                # Now the data model is at 0.28, so give it the appropriate version
                self._data['version'] = 0.28

            if self._data['version'] == 0.28:
                print("\n\nUpgrading data model from " + str(self._data['version']) + " to " + str(0.29))
                # Need to modify the data model from 0.28 up to 0.29
                # The "use_c_version" was added to the "user_settings" dictionary
                self._data['user_settings']['use_c_version'] = True
                # Now the data model is at 0.29, so give it the appropriate version
                self._data['version'] = 0.29

            if self._data['version'] == 0.29:
                print("\n\nUpgrading data model from " + str(self._data['version']) + " to " + str(0.30))
                # Need to modify the data model from 0.29 up to 0.30
                # The "poly_order" was added to the "scales" dictionary
                for scale_key in self._data['data']['scales'].keys():
                    scale = self._data['data']['scales'][scale_key]
                    scale['poly_order'] = 4
                # Now the data model is at 0.30, so give it the appropriate version
                self._data['version'] = 0.30

            if self._data['version'] == 0.30:
                print("\n\nUpgrading data model from " + str(self._data['version']) + " to " + str(0.31))
                # Need to modify the data model from 0.30 up to 0.31
                # The "skipped(1)" annotation is currently unused (now hard-coded in alignem.py)
                # Remove alll "skipped(1)" annotations since they can not otherwise be removed
                for scale_key in self._data['data']['scales'].keys():
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
                # Now the data model is at 0.31, so give it the appropriate version
                self._data['version'] = 0.31
            if self._data['version'] == 0.31:
                print("\n\nUpgrading data model from " + str(self._data['version']) + " to " + str(0.32))
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
            if self._data['version'] != self._current_version:
                # The data model could not be upgraded, so return a string with the error
                data_model = 'Version mismatch. Expected "' + str(
                    self._current_version) + '" but found ' + str(
                    self._data['version'])


    # def update_init_rot(self):
    #     image_scales_to_run = [self.get_scale_val(s) for s in sorted(self._data['data']['scales'].keys())]
    #     for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #         scale_key = self.get_scale_key(scale)
    #         for i, layer in enumerate(self._data['data']['scales'][scale_key]['alignment_stack']):
    #             layer['align_to_ref_method']['method_options'] = {'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION}
    #     logger.critical('cfg.DEFAULT_INITIAL_ROTATION = %f' % cfg.DEFAULT_INITIAL_ROTATION)
    #
    # def update_init_scale(self):
    #     image_scales_to_run = [self.get_scale_val(s) for s in sorted(self._data['data']['scales'].keys())]
    #     for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
    #         scale_key = self.get_scale_key(scale)
    #         for i, layer in enumerate(self._data['data']['scales'][scale_key]['alignment_stack']):
    #             layer['align_to_ref_method']['method_options'] = {'initial_scale': cfg.DEFAULT_INITIAL_SCALE}
    #     logger.critical('cfg.DEFAULT_INITIAL_SCALE = %f' % cfg.DEFAULT_INITIAL_SCALE)


    def clear_method_results(self, scale_key, start_layer=0):
        logger.info("Clearing 'method_results' Key")
        for layer in self._data['data']['scales'][scale_key]['alignment_stack'][start_layer:]:
            layer['align_to_ref_method']['method_results'] = {}

    def clear_match_points(self):
        logger.info("Deleting all match points for this layer")
        scale_key = self._data['data']['current_scale']
        layer_num = self._data['data']['current_layer']
        stack = self._data['data']['scales'][scale_key]['alignment_stack']
        layer = stack[layer_num]
        for role in layer['images'].keys():
            if 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata']['match_points'] = []
                layer['images'][role]['metadata']['annotations'] = []
        cfg.main_window.match_point_mode = False


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
