#!/usr/bin/env python3

import os
import sys
import time
import psutil
import config as cfg
# import src.alignem_utils as em
from .alignem_utils import get_scale_key, get_scale_val, getCurScale, areAlignedImagesGenerated, \
    makedirs_exist_ok, print_exception
# from qtpy.QtCore import QThread
from .image import BoundingRect, SetStackCafm
from .task_queue_mp import TaskQueue
from .remove_aligned_images import remove_aligned_images
from .save_bias_analysis import save_bias_analysis

__all__ = ['generate_aligned_images']

def generate_aligned_images(use_scale=None, start_layer=0, num_layers=-1):
    '''Called one time without arguments by 'do_alignment' '''
    print('generate_aligned_images >>>>>>>>')
    if use_scale == None:
        use_scale = get_scale_val(getCurScale())
    use_scale_key = get_scale_key(use_scale)
    # Ensure the directories exist to put aligned images into
    if areAlignedImagesGenerated():
        cfg.main_window.hud.post('Ensuring proper directory structure...')
        create_align_directories(use_scale=use_scale_kay)

    cfg.main_window.status.showMessage('Generating Images...')
    if areAlignedImagesGenerated():
        cfg.main_window.hud.post('Removing the Scale %s Images Generated in a Previous Run...' % use_scale)
        remove_aligned_images(start_layer=start_layer)
    cfg.main_window.hud.post('Generating Aligned Images (Applying Affines)...')

    cfg.main_window.hud.post('Propogating AFMs to generate CFMs at each layer...')
    # Propagate the AFMs to generate and appropriate CFM at each layer
    try:
        print("cfg.project_data['data']['scales'][use_scale_key]['null_cafm_trends'] = ")
        print(str(cfg.project_data['data']['scales'][use_scale_key]['null_cafm_trends']))
        null_biases = cfg.project_data['data']['scales'][use_scale_key]['null_cafm_trends']
    except:
        print_exception()
    # SetStackCafm ( cfg.project_data['data']['scales'][use_scale]['alignment_stack'], null_biases )
    SetStackCafm(cfg.project_data['data']['scales'][use_scale_key], null_biases=null_biases)
    destination_path = cfg.project_data['data']['destination_path']
    bias_data_path = os.path.join(destination_path, use_scale_key, 'bias_data')
    save_bias_analysis(cfg.project_data['data']['scales'][use_scale_key]['alignment_stack'], bias_data_path)  # <-- call to save bias data
    use_bounding_rect = cfg.project_data['data']['scales'][use_scale_key]['use_bounding_rect']

    with open(os.path.join(bias_data_path, 'bounding_rect.dat'), 'w') as file:  # Use file to refer to the file object
        if use_bounding_rect:
            rect = BoundingRect(cfg.project_data['data']['scales'][use_scale_key]['alignment_stack'])
            print("bounding rect size: '%d %d %d %d\n'" % (rect[0], rect[1], rect[2], rect[3]))
            file.write("%d %d %d %d\n" % (rect[0], rect[1], rect[2], rect[3]))
        else:
            file.write("None\n")

    # Finally generate the images with a parallel run of image_apply_affine.py
    task_queue = TaskQueue()
    cpus = min(psutil.cpu_count(logical=False), 48)
    task_queue.start(cpus)

    path = os.path.split(os.path.realpath(__file__))[0]
    # apply_affine_job = os.path.join(path, 'image_apply_affine.py')
    apply_affine_job = os.path.join(path, 'image_apply_affine.py')
    print("(tag) project_runnner | class=apply_affine_job=", apply_affine_job)
    alstack = cfg.project_data['data']['scales'][use_scale_key]['alignment_stack']

    if num_layers == -1:  end_layer = len(alstack)
    else:                 end_layer = start_layer + num_layers

    #  LOOP OVER THE STACK
    for layer in alstack[start_layer:end_layer + 1]:

        base_name = layer['images']['base']['filename']
        ref_name = layer['images']['ref']['filename']
        al_path, fn = os.path.split(base_name)
        al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = al_name
        cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']

        print('Running processes for: python image_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' )
        if use_bounding_rect:
            args = [
                    sys.executable,
                    apply_affine_job,
                    '-gray',
                    '-rect',
                    str(rect[0]),
                    str(rect[1]),
                    str(rect[2]),
                    str(rect[3]),
                    '-afm',
                    str(cafm[0][0]),
                    str(cafm[0][1]),
                    str(cafm[0][2]),
                    str(cafm[1][0]),
                    str(cafm[1][1]),
                    str(cafm[1][2]),
                    base_name,
                    al_name
            ]
        else:
            args = [
                    sys.executable,
                    apply_affine_job,
                    '-gray',
                    '-afm',
                    str(cafm[0][0]),
                    str(cafm[0][1]),
                    str(cafm[0][2]),
                    str(cafm[1][0]),
                    str(cafm[1][1]),
                    str(cafm[1][2]),
                    base_name,
                    al_name
            ]
        task_queue.add_task(args)

    cfg.main_window.hus.post('Running ImageApplyAffine to Generate Aligned Images...')
    t0 = time.time()
    task_queue.collect_results()
    dt = time.time() - t0
    cfg.main_window.hus.post('Image Generation (ImageApplyAffine) Completed in %.2f seconds' % (dt))
    task_queue.stop()
    del task_queue

    cfg.main_window.hud.post('Wrapping up...')
    cfg.main_window.center_all_images()
    cfg.main_window.update_win_self()
    cfg.main_window.save_project()
    cfg.main_window.hud.post('Complete.')

    print('<<<<<<<< generate_aligned_images')
    print('\nImage Generation Complete\n')

def create_align_directories(use_scale):
    source_dir = os.path.join(cfg.project_data['data']['destination_path'], use_scale, "img_src")
    makedirs_exist_ok(source_dir, exist_ok=True)
    target_dir = os.path.join(cfg.project_data['data']['destination_path'], use_scale, "img_aligned")
    makedirs_exist_ok(target_dir, exist_ok=True)