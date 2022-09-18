#!/usr/bin/env python3

import os
import psutil
import inspect
import logging
import threading
import concurrent
from qtpy.QtGui import QPixmap
import qimage2ndarray
import numpy as np
import dask.array as da
import src.config as cfg
from helpers import get_scale_val, print_exception

__all__ = ['SmartImageLibrary']

logger = logging.getLogger(__name__)


class SmartImageLibrary:
    """A class containing multiple images keyed by their file name."""

    def __init__(self):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True
        self.initial_memory = psutil.virtual_memory()
        self.prev_scale_val = None
        self.prev_layer_index = None
        self.print_switch = False
        '''Should default to 5 times number of processors'''
        self.executors = concurrent.futures.ThreadPoolExecutor(max_workers=None)  # (<--*)

    def pathkey(self, file_path):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def __str__(self):
        s = "ImageLibrary contains %d images\n" % len(self._images)
        for k, v in self._images.items():
            s += "  " + k + "\n"
            s += "    loaded:  " + str(v['loaded']) + "\n"
            s += "    loading: " + str(v['loading']) + "\n"
            s += "    task:    " + str(v['task']) + "\n"
            s += "    image:   " + str(v['image']) + "\n"
        logger.info(s)
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        return ("ImageLibrary contains ...")

    def remove_image_reference(self, file_path):
        # Do nothing since the smart image library now makes this decision internally
        pass

    def remove_all_images(self):
        # Do nothing since the smart image library now makes this decision internally
        pass

    def get_image_reference(self, file_path):
        ''''Called by: ZoomPanWidget.center_image, ZoomPanWidget.paintEvent'''
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    image_ref = self._images[real_norm_path]['image']
                else:
                    # The image is still loading, so return None
                    image_ref = None
            else:
                # The image is not in the library at all, so start loading it now (but don't wait)
                logger.debug("  Begin loading image: \"" + str(real_norm_path) + "\"")
                self.queue_image_read(real_norm_path)
                image_ref = self._images[real_norm_path]['image']
        return image_ref

    def get_image_reference_if_loaded(self, file_path):
        return self.get_image_reference(file_path)

    def queue_image_read(self, file_path):
        '''called by self.make_available, self.get_image_reference, self.update, '''
        logger.info("top of queue_image_read ( " + file_path + ")")
        real_norm_path = self.pathkey(file_path)
        self._images[real_norm_path] = {'image': None, 'loaded': False, 'loading': True, 'task': None}
        if self.print_switch: logger.debug("submit with (" + real_norm_path + ", " + str(self._images[real_norm_path]) + ")")
        task_future = self.executors.submit(image_loader, real_norm_path, self._images[real_norm_path])
        # task_future.add_done_callback(image_completed_loading) #0701
        if self.print_switch: logger.debug("  task_future: " + str(task_future))
        self._images[real_norm_path]['task'] = task_future

    def make_available(self, requested):
        """
        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """
        logger.debug("Making image available: " + str(sorted([str(s[-7:]) for s in requested])))
        already_loaded = set(self._images.keys())
        normalized_requested = set([self.pathkey(f) for f in requested])
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        try:
            for f in need_to_unload:
                self.remove_image_reference(f)
            for f in need_to_load:
                if self.threaded_loading_enabled:
                    self.queue_image_read(f)  # Using this will enable threaded reading behavior
                else:
                    self.get_image_reference(f)  # Using this will force sequential reading behavior
            logger.debug("Library has " + str(len(self._images.keys())) + " images")
        except:
            print_exception()
            logger.warning('Failed to make image available')


    def update(self):
        cur_scale_key = cfg.data['data']['current_scale']
        cur_scale_val = get_scale_val(cur_scale_key)
        cur_layer_index = cfg.data['data']['current_layer']
        # scale_keys = sorted(cfg.data['data']['scales'].keys())
        # scale_vals = sorted(scale_val(scale_key) for scale_key in scale_keys)
        # cur_stack = cfg.data['data']['scales'][cur_scale_key]['alignment_stack']
        # layer_nums = range(len(cur_stack))
        # amem = psutil.virtual_memory().available
        # if self.print_switch: logger.info("Looking at: scale " + str(cur_scale_val) + " in " + str(scale_vals) + ", layer " + str(
        #     cur_layer_index) + " in " + str(layer_nums) +
        #       ", Available Memory = " + str(amem) + " out of " + str(self.initial_memory.available))

        try:
            stack = cfg.data['data']['scales'][cfg.data['data']['current_scale']]['alignment_stack']
            layer = stack[cfg.data['data']['current_layer']]
            for k in layer['images'].keys():
                logger.info("Loading role " + k)
                try:
                    fn = layer['images'][k]['filename']
                    if (fn != None) and (len(fn) > 0):
                        logger.info("Loading file " + fn)
                        self.queue_image_read(fn)
                except:
                    pass
        except:
            pass

        self.prev_scale_val = cur_scale_val
        self.prev_layer_index = cur_layer_index