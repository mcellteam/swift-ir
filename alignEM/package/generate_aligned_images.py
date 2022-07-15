#!/usr/bin/env python3

import os
import sys
import time
import psutil
import logging
from qtpy.QtCore import QThread
import config as cfg

from .em_utils import get_scale_key, get_scale_val, get_cur_scale_key, are_aligned_images_generated, \
    makedirs_exist_ok, print_exception, get_num_imported_images, get_num_scales
from .mp_queue import TaskQueue
from .remove_aligned_images import remove_aligned_images
from .save_bias_analysis import save_bias_analysis
from .image_funcs import *

# FROM WORKING EXAMPLE
# import os
# import sys
# import time
# import psutil
# import config as cfg
# # import src.alignem_utils as em
# from .glanceem_utils import get_scale_key, get_scale_val, getCurScale, areAlignedImagesGenerated, \
#     makedirs_exist_ok, print_exception
# # from qtpy.QtCore import QThread
# # from .image import BoundingRect, SetStackCafm
# from .task_queue_mp import TaskQueue
# from .remove_aligned_images import remove_aligned_images
# from .save_bias_analysis import save_bias_analysis


__all__ = ['generate_aligned_images']

logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt='%H:%M:%S',
        handlers=[ logging.StreamHandler() ]
)

def generate_aligned_images(use_scale=None, start_layer=0, num_layers=-1):
    '''Called one time without arguments by 'do_alignment' '''
    logging.info('\ngenerate_aligned_images >>>>>>>>\n')
    QThread.currentThread().setObjectName('ApplyAffines')
    cfg.main_window.read_gui_update_project_data()
    scale_key = get_scale_key(use_scale)
    # create_align_directories(use_scale=scale_key)
    cfg.main_window.hud.post('Generating Aligned Images (Applying Affines)...')
    if are_aligned_images_generated():
        cfg.main_window.hud.post('Removing the Scale %s Images Generated in a Previous Run...' % use_scale)
        remove_aligned_images(start_layer=start_layer)
    cfg.main_window.hud.post('Propogating AFMs to generate CFMs at each layer...')
    scale_dict = cfg.project_data['data']['scales'][scale_key]
    null_bias = cfg.project_data['data']['scales'][get_cur_scale_key()]['null_cafm_trends']

    print('generate_aligned_images | str(null_bias) = %s' % str(null_bias))
    print('Calling SetStackCafm with args...')
    print('null_bias = %s' % str(null_bias))
    print('type(null_bias) = %s' % type(null_bias))
    print('scale_dict = %s' % str(scale_dict))

    try:
        SetStackCafm(scale_dict=scale_dict, null_biases=null_bias)
    except:
        print_exception()
    destination_path = cfg.project_data['data']['destination_path']
    bias_data_path = os.path.join(destination_path, scale_key, 'bias_data')
    logging.info('generate_aligned_images | bias (.dat) path=%s' % bias_data_path)
    # try:
    #     save_bias_analysis(cfg.project_data['data']['scales'][scale_key]['alignment_stack'], bias_data_path)
    # except:
    #     print_exception()
    use_bounding_rect = cfg.project_data['data']['scales'][scale_key]['use_bounding_rect']
    with open(os.path.join(bias_data_path, 'bounding_rect.dat'), 'w') as file:
        if use_bounding_rect:
            rect = BoundingRect(cfg.project_data['data']['scales'][scale_key]['alignment_stack'])
            logging.info("bounding rect size: '%d %d %d %d\n'" % (rect[0], rect[1], rect[2], rect[3]))
            file.write("%d %d %d %d\n" % (rect[0], rect[1], rect[2], rect[3]))
        else:
            file.write("None\n")

    logging.info('Generating aligned images with parallel run of job_apply_affine...')
    # Generate the images with a parallel run of job_apply_affine.py
    task_queue = TaskQueue(n_tasks=get_num_imported_images())
    cpus = min(psutil.cpu_count(logical=False), 48)
    task_queue.start(cpus)
    path = os.path.split(os.path.realpath(__file__))[0]
    apply_affine_job = os.path.join(path, 'job_apply_affine.py')
    logging.info('generate_aligned_images | path =' + str(path))
    logging.info('generate_aligned_images | job path = %s' % apply_affine_job)
    alstack = cfg.project_data['data']['scales'][scale_key]['alignment_stack']
    if num_layers == -1:  end_layer = len(alstack)
    else:  end_layer = start_layer + num_layers
    for layer in alstack[start_layer:end_layer + 1]:
        base_name = layer['images']['base']['filename']
        ref_name = layer['images']['ref']['filename']
        al_path, fn = os.path.split(base_name)
        logging.info('generate_aligned_images | basename=%s, ref_name=%s, al_path=%s, fn=%s' % (base_name,ref_name,al_path,fn))

        '''(FROM AN INITIAL ALIGN)
        INFO:root:generate_aligned_images | 
            basename=/Users/joelyancey/glanceEM_SWiFT/test_projects/testttttttt/scale_4/img_src/R34CA1-BS12.114.tif, 
            ref_name=/Users/joelyancey/glanceEM_SWiFT/test_projects/testttttttt/scale_4/img_src/R34CA1-BS12.113.tif, 
            al_path=/Users/joelyancey/glanceEM_SWiFT/test_projects/testttttttt/scale_4/img_src, fn=R34CA1-BS12.114.tif

        '''


        '''(FROM A REGENERATE:)
        INFO:root:generate_aligned_images | 
            basename=/Users/joelyancey/glanceEM_SWiFT/test_projects/testttt/scale_4/img_src/R34CA1-BS12.107.tif, 
            ref_name=/Users/joelyancey/glanceEM_SWiFT/test_projects/testttt/scale_4/img_src/R34CA1-BS12.106.tif, 
            al_path=/Users/joelyancey/glanceEM_SWiFT/test_projects/testttt/scale_4/img_src, fn=R34CA1-BS12.107.tif

        '''

        al_name = os.path.join(os.path.split(al_path)[0], 'img_aligned', fn)
        layer['images']['aligned'] = {}
        layer['images']['aligned']['filename'] = al_name
        cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']
        logging.info('Running processes for: python job_apply_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' )
        if use_bounding_rect:
            args = [ sys.executable, apply_affine_job, '-gray', '-rect',
                    str(rect[0]), str(rect[1]), str(rect[2]), str(rect[3]), '-afm', str(cafm[0][0]), str(cafm[0][1]),
                    str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
        else:
            args = [sys.executable, apply_affine_job, '-gray', '-afm', str(cafm[0][0]), str(cafm[0][1]),
                    str(cafm[0][2]), str(cafm[1][0]), str(cafm[1][1]), str(cafm[1][2]), base_name, al_name]
        task_queue.add_task(args)

    logging.info('Running ImageApplyAffine to Generate Aligned Images...')
    cfg.main_window.hud.post('Running ImageApplyAffine to Generate Aligned Images...')
    t0 = time.time()
    try:
        task_queue.collect_results()
    except:
        logging.info('generate_aligned_images | task_queue.collect_results() encountered a problem',logging.WARNING)
        print_exception()
    dt = time.time() - t0
    cfg.main_window.hud.post('Image Generation (ImageApplyAffine) Completed in %.2f seconds' % dt)
    task_queue.stop()
    del task_queue

    bias_data_path = os.path.join(cfg.project_data['data']['destination_path'], use_scale, 'bias_data')
    save_bias_analysis(cfg.project_data['data']['scales'][use_scale]['alignment_stack'], bias_data_path)  # <-- call to save bias data

    cfg.main_window.hud.post('Wrapping up...')
    cfg.main_window.center_all_images()
    cfg.main_window.update_win_self()
    cfg.main_window.refresh_all_images()
    logging.info('<<<<<<<< generate_aligned_images')
    print('\nImage Generation Complete\n')

def create_align_directories(use_scale):
    source_dir = os.path.join(cfg.project_data['data']['destination_path'], use_scale, "img_src")
    makedirs_exist_ok(source_dir, exist_ok=True)
    target_dir = os.path.join(cfg.project_data['data']['destination_path'], use_scale, "img_aligned")
    makedirs_exist_ok(target_dir, exist_ok=True)