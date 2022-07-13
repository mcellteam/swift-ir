#!/usr/bin/env python3

import os
import sys
import shutil
import platform
import psutil
import time
import logging
from qtpy.QtCore import QThread
import config as cfg
import package.em_utils as em
from .mp_queue import TaskQueue

__all__ = ['generate_scales']

logger = logging.getLogger(__name__)
logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt='%H:%M:%S',
        handlers=[ logging.StreamHandler() ]
)

def generate_scales(progress_callback=None):
    print("generate_scales >>>>>>>>")
    #todo come back to this #0406
    # try:
    #     self.scales_combobox.disconnect()
    # except Exception:
    #     print(
    #         "BenignException: could not disconnect scales_combobox from handlers or nothing to disconnect. Continuing...")

    #0531 TODO: NEED TO HANDLE CHANGING OF NUMBER OF SCALES, ESPECIALLY WHEN DECREASED. MUST REMOVE PRE-EXISTING DATA (bias data, scaled images, and aligned images)

    logging.info('generate_scales >>>>>>>>')
    QThread.currentThread().setObjectName('ScaleImages')
    cfg.main_window.hud.post('Preparing to Generate Scale Image Hierarchy...')
    # progress_callback.emit(50)
    n_images = em.get_num_imported_images()
    n_scales = em.get_num_scales()
    n_tasks = n_images * (n_scales+1)
    image_scales_to_run = [em.get_scale_val(s) for s in sorted(cfg.project_data['data']['scales'].keys())]
    logging.info("generate_scales | Scale Factors : " + str(image_scales_to_run))
    logging.info("generate_scales | # of Images   : ", n_images)

    scaling_queue = TaskQueue(n_tasks=n_tasks)
    # scaling_queue = TaskQueue()
#0709    # scaling_queue = task_queue.TaskQueue(n_tasks=n_images, progress_callback=progress_callback)

    cpus = min(psutil.cpu_count(logical=False), 48)
    my_path = os.path.split(os.path.realpath(__file__))[0] + '/'
    my_system = platform.system()
    my_node = platform.node()
    logging.info("generate_scales | # cpus        :" % cpus)
    logging.info("generate_scales | my_path       :" % my_path)
    logging.info("generate_scales | my_system     :" % my_system)
    logging.info("generate_scales | my_node       :" % my_node)
    logging.info('generate_scales | Starting the scaling queue...')
    scaling_queue.start(cpus)  # cpus = 8 for my laptop
    cfg.main_window.hud.post("Configuring platform-specific path to SWiFT-IR executables")
    '''TODO: Check for SWiFT-IR executables at startup'''
    if my_system == 'Darwin':
        iscale2_c = os.path.join(my_path, 'lib/bin_darwin/iscale2')
        logging.info('iscale2_c = %s' % iscale2_c)
    elif my_system == 'Linux':
        if '.tacc.utexas.edu' in my_node:
            iscale2_c = os.path.join(my_path, 'lib/bin_tacc/iscale2')
        else:
            iscale2_c = os.path.join(my_path, 'lib/bin_linux/iscale2')


    # my path = / Users / joelyancey / glanceem_swift / swift - ir / source / alignEM / package / src /
    # iscale2_c path = / lib / bin_darwin / iscale2

    try:
        logging.info('Checking if iscale_2 (%s) is a file...' % iscale2_c)
        os.path.isfile(iscale2_c)
    except:
        cfg.main_window.hud.post('iscale2_c Executable Was Not Found At Path %s. It Must Be Compiled.' % iscale2_c, logging.ERROR)
        logging.warning('generate_scales | EXCEPTION | iscale2_c Executable Was Not Found At Path')
        return


    cfg.main_window.hud.post("Creating project directory structure...")
    try:
        for scale in sorted(image_scales_to_run):
            scale_key = em.get_scale_key(scale)
            subdir_path = os.path.join(cfg.project_data['data']['destination_path'], scale_key)
            em.create_project_structure_directories(subdir_path)
    except:
        cfg.main_window.hud.post("There was a problem creating the directory structure", logging.ERROR)
        return

    for scale in sorted(image_scales_to_run):  # i.e. string '1 2 4'
        cfg.main_window.hud.post("Preparing to generate images for scale " + str(scale))
        scale_key = em.get_scale_key(scale)
        # scale_key = str(scale)
        # if not 'scale_' in scale_key:
        #     scale_key = 'scale_' + scale_key
        for layer in cfg.project_data['data']['scales'][scale_key]['alignment_stack']:
            # Remove previously aligned images from panel ??

            # Copy (or link) the source images to the expected scale_key"/img_src" directory
            for role in layer['images'].keys():
                # Only copy files for roles "ref" and "base"
                if role in ['ref', 'base']:
                    # print("  Generating images for scale : " + str(scale) + "  layer: "\
                    #       + str(cfg.project_data['data']['scales'][scale_key]['alignment_stack'].index(layer))\
                    #       + "  role: " + str(role))
                    base_file_name = layer['images'][role]['filename']
                    if base_file_name != None:
                        if len(base_file_name) > 0:
                            abs_file_name = os.path.abspath(base_file_name)
                            bare_file_name = os.path.split(abs_file_name)[1]
                            destination_path = os.path.abspath(cfg.project_data['data']['destination_path'])
                            outfile_name = os.path.join(destination_path, scale_key, 'img_src', bare_file_name)
                            if scale == 1:
                                if em.get_best_path(abs_file_name) != em.get_best_path(outfile_name):
                                    # The paths are different so make the link
                                    try:
                                        # print("generate_scales | UnLinking " + outfile_name)
                                        os.unlink(outfile_name)
                                    except:
                                        pass
                                        # print("generate_scales | Error UnLinking " + outfile_name)
                                    try:
                                        # print("generate_scales | Linking from " + abs_file_name + " to " + outfile_name)
                                        os.symlink(abs_file_name, outfile_name)
                                    except:
                                        logging.warning("generate_scales | Unable to link from " + abs_file_name + " to " + outfile_name)
                                        logging.warning("generate_scales | Copying file instead")
                                        # Not all operating systems allow linking for all users (Windows 10, for example, requires admin rights)
                                        try:
                                            shutil.copy(abs_file_name, outfile_name)
                                        except:
                                            logging.warning("generate_scales | Unable to link or copy from " + abs_file_name + " to " + outfile_name)
                            else:
                                try:
                                    # Do the scaling
                                    # print(
                                    #     "Copying and scaling from " + abs_file_name + " to " + outfile_name + " by " + str(
                                    #         scale))

                                    if os.path.split(os.path.split(os.path.split(abs_file_name)[0])[0])[
                                        1].startswith('scale_'):
                                        # Convert the source from whatever scale is currently processed to scale_1
                                        p, f = os.path.split(abs_file_name)
                                        p, r = os.path.split(p)
                                        p, s = os.path.split(p)
                                        abs_file_name = os.path.join(p, 'scale_1', r, f)

                                    code_mode = 'c'  # force c code scaling implementation

                                    if code_mode == 'python':
                                        scaling_queue.add_task(cmd=sys.executable,
                                                               args=['job_single_scale.py', str(scale),
                                                                     str(abs_file_name), str(outfile_name)], wd='.')
                                    else:
                                        scale_arg = '+%d' % (scale)
                                        outfile_arg = 'of=%s' % (outfile_name)
                                        infile_arg = '%s' % (abs_file_name)
                                        #                        scaling_queue.add_task (cmd=iscale2_c, args=[scale_arg, outfile_arg, infile_arg], wd='.')
                                        scaling_queue.add_task([iscale2_c, scale_arg, outfile_arg, infile_arg])

                                    # These two lines generate the scales directly rather than through the queue
                                    # img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage(abs_file_name), fac=scale )
                                    # align_swiftir.swiftir.saveImage ( img, outfile_name )

                                    # Change the base image for this scale to the new file
                                    layer['images'][role]['filename'] = outfile_name
                                except:
                                    cfg.main_window.hud.post("Error adding tasks to the task queue - Canceling", logging.ERROR)
                                    em.print_exception()
                                    return

                            # Update the Data Model with the new absolute file name. This replaces the originally opened file names
                            # print("generate_scales | Original File Name: " + str(layer['images'][role]['filename']))
                            layer['images'][role]['filename'] = outfile_name
                            # print("generate_scales | Updated  File Name: " + str(layer['images'][role]['filename']))

    ### Join the queue here to ensure that all have been generated before returning
    # scaling_queue.work_q.join() # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    cfg.main_window.hud.post('Generating scale image hierarchy...')
    t0 = time.time()
    scaling_queue.collect_results()  # It might be better to have a TaskQueue.join method to avoid knowing "inside details" of class
    scaling_queue.stop()
    del scaling_queue
    dt = time.time() - t0
    cfg.main_window.hud.post("Scaling completed in %.2f seconds" % dt)
    print('<<<<<<<< generate_scales')

