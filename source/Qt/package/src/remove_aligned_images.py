#!/usr/bin/env python3

import os
import config as cfg
import src.alignem_utils as em

__all__ = ['remove_aligned_images']

def remove_aligned_images(start_layer=0, clear_results=True, use_scale=None):
    # print('\nremove_aligns:')
    # print("remove_aligns(start_layer=%d, prompt=%s, clear_results=%s):" % (start_layer, str(prompt), str(clear_results)))

    # disconnecting 'prompt' and 'actually_remove' variables and checks - Todo: rewrite warnings using glanceem_utils functions

    # use_scale = em.getCurScale()
    # print("remove_aligns | Removing aligned from scale %s forward from layer %s" % (use_scale[-1], str(start_layer)))
    print('remove_aligns >>>>>>>>')
    if use_scale == None:  use_scale = em.getCurScale()
    if em.areAlignedImagesGenerated():
        cfg.main_window.hud.post('Removing previously generated images for Scale %s...' % use_scale[-1])
    start_layer = 0
    clear_results = True
    delete_list = []
    layer_index = 0
    n = len(cfg.project_data['data']['scales'][use_scale]['alignment_stack'])
    for layer in cfg.project_data['data']['scales'][use_scale]['alignment_stack']:
        if layer_index >= start_layer:
            # print("Removing Aligned from Layer " + str(layer_index))
            if 'aligned' in layer['images'].keys():
                delete_list.append(layer['images']['aligned']['filename'])
                # print("  Removing " + str(layer['images']['aligned']['filename']))
                layer['images'].pop('aligned')

                if clear_results:
                    # Remove the method results since they are no longer applicable
                    if 'align_to_ref_method' in layer.keys():
                        if 'method_results' in layer['align_to_ref_method']:
                            #0619pm
                            # Set the "method_results" to an empty dictionary to signify no results:
                            layer['align_to_ref_method']['method_results'] = {}
        layer_index += 1

    # cfg.image_library.remove_all_images()

    for fname in delete_list:
        if fname != None:
            if os.path.exists(fname):
                os.remove(fname)
                cfg.image_library.remove_image_reference(fname)

    print('<<<<<<<< remove_aligns')