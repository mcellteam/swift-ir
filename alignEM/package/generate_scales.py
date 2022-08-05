#!/usr/bin/env python3

import os
import sys
import shutil
import platform
import psutil
import time
import logging
from qtpy.QtCore import QThread
import package.config as cfg
from package.em_utils import print_exception, get_num_imported_images, get_num_scales, get_scale_val, get_scale_key, \
    create_project_structure_directories, get_best_path, get_scales_list
from .mp_queue import TaskQueue

__all__ = ['generate_scales']

logger = logging.getLogger(__name__)


def generate_scales(progress_callback=None):
    QThread.currentThread().setObjectName('ScaleImages')
    print('_____________Generate Scales Begin_____________')
    
    image_scales_to_run = [get_scale_val(s) for s in sorted(cfg.project_data['data']['scales'].keys())]
    logger.info("Scale Factors : %s" % str(image_scales_to_run))
    proj_path = cfg.project_data['data']['destination_path']
    # scale_q = TaskQueue(n_tasks=get_num_imported_images() * (get_num_scales() + 1)) #0802
    scale_q = TaskQueue(n_tasks=get_num_imported_images() * (get_num_scales()))
    cpus = min(psutil.cpu_count(logical=False), 48)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    my_system = platform.system()
    my_node = platform.node()
    cfg.main_window.hud.post("Configuring platform-specific path to SWiFT-IR executables")
    '''TODO: Check for SWiFT-IR executables at startup'''
    '''TODO: Keep local current scale value as member of MainWindow class, to reduce read ops.'''
    if my_system == 'Darwin':
        bindir = 'bin_darwin'
    elif my_system == 'Linux':
        bindir = 'bin_tacc' if '.tacc.utexas.edu' in my_node else 'bin_linux'
    else:
        logger.error("System Could Not Be Resolved - Exiting")
        return
    iscale2_c = os.path.join(my_path, 'lib', bindir, 'iscale2')
    try:
        logger.info('Checking if iscale_2 (%s) is a file...' % iscale2_c)
        os.path.isfile(iscale2_c)
    except:
        print_exception()
        cfg.main_window.hud.post("'iscale2_c' Not Found At Path %s. It Must Be Compiled." % iscale2_c, logging.ERROR)
        return
    
    cfg.main_window.hud.post("Creating Project Directory Structure...")
    logger.info('image_scales_to_run = %s' % str(image_scales_to_run))
    try:
        # for scale in sorted(image_scales_to_run):
        for scale in get_scales_list():
            subdir_path = os.path.join(proj_path, scale)
            create_project_structure_directories(subdir_path)
    except:
        print_exception()
        cfg.main_window.hud.post("There was a problem creating the directory structure", logging.WARNING)
        return

    #0804+
    # if str(image_scales_to_run) == '[1]':
    #     logger.info('Only one scale is requested... not calling task_queue')
    #     return
    
    scale_q.start(cpus)
    
    for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
        print('Loop: scale = ', scale)
        cfg.main_window.hud.post("Preparing to generate images for scale " + str(scale))
        scale_key = get_scale_key(scale)
        for i, layer in enumerate(cfg.project_data['data']['scales'][scale_key]['alignment_stack']):
            fn = os.path.abspath(layer['images']['base']['filename'])
            ofn = os.path.join(proj_path, scale_key, 'img_src', os.path.split(fn)[1])

            layer['align_to_ref_method']['method_options'] = {'initial_rotation': cfg.DEFAULT_INITIAL_ROTATION}
            layer['align_to_ref_method']['method_options'] = {'initial_scale': cfg.DEFAULT_INITIAL_SCALE}

            if scale == 1:

                '''Scale 1 Only'''
                if get_best_path(fn) != get_best_path(ofn):
                    # The paths are different so make the link
                    try:
                        os.unlink(ofn)
                    except:
                        pass
                    try:
                        os.symlink(fn, ofn)
                    except:
                        # Not all operating systems allow linking for all users (Windows 10 requires admin rights)
                        logger.warning("Unable to link from %s to %s. Copying instead." % (fn, ofn))
                        try:
                            shutil.copy(fn, ofn)
                        except:
                            logger.warning("Unable to link or copy from " + fn + " to " + ofn)
            else:
                '''All Scales Other Than 1'''

                try:
                    if os.path.split(os.path.split(os.path.split(fn)[0])[0])[1].startswith('scale_'):
                        '''This is run only when re-scaling'''
                        # Convert the source from whatever scale is currently processed to scale_1
                        p, f = os.path.split(fn)
                        p, r = os.path.split(p)
                        p, s = os.path.split(p)
                        fn = os.path.join(p, 'scale_1', r, f)
                        if i == 1:
                            print('\nfn = ', fn)
                            print('p = ', p)
                            print('r = ', r)
                            print('s = ', s)
                            print(fn)
                    
                    if cfg.CODE_MODE == 'python':
                        scale_q.add_task(cmd=sys.executable,
                                         args=['job_single_scale.py', str(scale), str(fn), str(ofn)], wd='.')
                    else:
                        scale_arg = '+%d' % (scale)
                        outfile_arg = 'of=%s' % (ofn)
                        infile_arg = '%s' % (fn)
                        # scale_q.add_task (cmd=iscale2_c, args=[scale_arg, outfile_arg, infile_arg], wd='.')
                        scale_q.add_task([iscale2_c, scale_arg, outfile_arg, infile_arg])
                        if i == 1:
                            print('\n____generate_scales____\nscale_q Parameters (Example):')
                            print('1: %s\n2: %s\n3: %s\n4: %s\n' % (iscale2_c, scale_arg, outfile_arg, infile_arg))
                        '''
                        ____scale_q Parameters (Example)____
                        (1) : iscale2_c : /Users/joelyancey/glanceem_swift/swift-ir/alignEM/package/lib/bin_darwin/iscale2
                        (2) : scale_arg : +2
                        (3) : outfile_arg : of=/Users/joelyancey/glanceEM_SWiFT/test_projects/test993/scale_2/img_src/R34CA1-BS12.104.tif
                        (4) : infile_arg : /Users/joelyancey/glanceEM_SWiFT/test_images/r34_tifs/R34CA1-BS12.104.tif
            
                        '''
                    
                    # generate the scales directly rather than through the queue
                    # img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(fn), fac=scale )
                    # align_swiftir.swiftir.saveImage ( img, ofn )
                    
                    # Change the base image for this scale to the new file
                    layer['images']['base']['filename'] = ofn
                except:
                    cfg.main_window.hud.post("Error adding tasks to the task queue - Canceling", logging.ERROR)
                    print_exception()
                    return
            
            layer['images']['base']['filename'] = ofn  # Update Data Model
            '''Example:
            Original File Name: /Users/joelyancey/glanceEM_SWiFT/test_images/r34_tifs/R34CA1-BS12.106.tif
            Updated  File Name: /Users/joelyancey/glanceEM_SWiFT/test_projects/test991/scale_1/img_src/R34CA1-BS12.106.tif'''
    
    ### Join the queue here to ensure that all have been generated before returning
    # scale_q.work_q.join() # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    cfg.main_window.hud.post('Generating scale image hierarchy...')
    t0 = time.time()
    scale_q.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    scale_q.stop()
    del scale_q
    dt = time.time() - t0
    cfg.main_window.hud.post("Scaling completed in %.2f seconds" % dt)
    
    print('_____________Generate Scales End_____________')
