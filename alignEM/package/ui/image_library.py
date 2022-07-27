#!/usr/bin/env python3

import os
import psutil
import inspect
import logging
import threading
import concurrent
from qtpy.QtGui import QPixmap
import package.config as cfg
from ..em_utils import get_scale_val

__all__ = ['ImageLibrary','SmartImageLibrary']

logger = logging.getLogger(__name__)

class ImageLibrary:
    """ THIS IS THE CLASS CURRENTLY IN USE, INITIALIZED WITH NAME 'image_library'
    A class containing multiple images keyed by their file name."""

    def __init__(self):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True

    def pathkey(self, file_path):
        if file_path == None:
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def print_load_status(self):

        logger.debug("  Library has " + str(len(self._images.keys())) + " images")
        logger.debug("  Names:   " + str(sorted([str(s[-7:]) for s in self._images.keys()])))
        logger.debug("  Loaded:  " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loaded']])))
        logger.debug("  Loading: " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loading']])))


    def __str__(self):
        s = "ImageLibrary contains %d images\n" % len(self._images)
        keys = sorted(self._images.keys())
        for k in keys:
            v = self._images[k]
            s += "  " + k + "\n"
            s += "    loaded:  " + str(v['loaded']) + "\n"
            s += "    loading: " + str(v['loading']) + "\n"
            s += "    task:    " + str(v['task']) + "\n"
            s += "    image:   " + str(v['image']) + "\n"
        # print ( s )
        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        return (s)

    def get_image_reference(self, file_path):
        # logger.info("Getting image reference | Caller: " + inspect.stack()[1].function + " |  ImageLibrary.get_image_reference")
        # print_debug(50, "get_image_reference ( " + str(file_path) + " )")
        self.print_load_status()
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                # print_debug(50, "  Image name is in the library")
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    # print_debug(50, "  Image was already loaded")
                    image_ref = self._images[real_norm_path]['image']
                elif self._images[real_norm_path]['loading']:
                    # The image is still loading, so wait for it to complete
                    # print_debug(4, "  Image still loading ... wait")
                    self._images[real_norm_path]['task'].join()
                    self._images[real_norm_path]['task'] = None
                    self._images[real_norm_path]['loaded'] = True
                    self._images[real_norm_path]['loading'] = False
                    image_ref = self._images[real_norm_path]['image']
                else:
                    # print_debug(3, "  Load Warning for: \"" + str(real_norm_path) + "\"")
                    image_ref = self._images[real_norm_path]['image']
            else:
                # The image is not in the library at all, so force a load now (and wait)
                # print_debug(4, "  Forced load of image: \"" + str(real_norm_path) + "\"") #0606

                #0526
                # image = QImage(real_norm_path)
                # self._images[real_norm_path] = {'image': QPixmap.fromImage(image).scaled(200, 200), 'loaded': True, 'loading': False,'task': None}

                self._images[real_norm_path] = {'image': QPixmap(real_norm_path), 'loaded': True, 'loading': False,'task': None} #orig
                image_ref = self._images[real_norm_path]['image']
        return image_ref

    # Caller = paintEvent. Loads each image.
    def get_image_reference_if_loaded(self, file_path):
        # logger.info("Getting image reference if loaded | Caller: " + inspect.stack()[1].function + " |  ImageLibrary.get_image_reference_if_loaded")
        image_ref = None
        real_norm_path = self.pathkey(file_path)
        if real_norm_path != None:
            # This is an actual path
            if real_norm_path in self._images:
                # This file is already in the library ... it may be complete or still loading
                if self._images[real_norm_path]['loaded']:
                    # The image is already loaded, so return it
                    image_ref = self._images[real_norm_path]['image']
                elif self._images[real_norm_path]['loading']:
                    # The image is still loading, so wait for it to complete
                    self._images[real_norm_path]['task'].join()
                    self._images[real_norm_path]['task'] = None
                    self._images[real_norm_path]['loaded'] = True
                    self._images[real_norm_path]['loading'] = False
                    image_ref = self._images[real_norm_path]['image']
                else:
                    logger.warning("  Load Warning for: \"" + str(real_norm_path) + "\"")
                    image_ref = self._images[real_norm_path]['image']
        return image_ref

    def remove_image_reference(self, file_path):
        logger.info("  ImageLayer is removing image reference (called by " + inspect.stack()[1].function + ")...")
        image_ref = None
        if not (file_path is None):
            real_norm_path = self.pathkey(file_path)
            if real_norm_path in self._images:
                # print_debug ( 4, "ImageLibrary > remove_image_reference... Unloading image: \"" + real_norm_path + "\"" )
                image_ref = self._images.pop(real_norm_path)['image']
        # This returned value may not be valid when multi-threading is implemented
        return image_ref

    # Load the image
    def load_image_worker(self, real_norm_path, image_dict):
        logger.debug("load_image_worker started with:", str(real_norm_path))
        image_dict['image'] = QPixmap(real_norm_path) # no class
        image_dict['loaded'] = True
        image_dict['loading'] = False
        logger.debug("load_image_worker finished for:" + str(real_norm_path))
        cfg.image_library.print_load_status()

    def queue_image_read(self, file_path):
        # logger.info("Queuing image read | Caller: " + inspect.stack()[1].function + " |  ImageLibrary.queue_image_read")
        real_norm_path = self.pathkey(file_path)
        logger.debug("  start queue_image_read with: \"" + str(real_norm_path) + "\"")
        self._images[real_norm_path] = {'image': None, 'loaded': False, 'loading': True, 'task': None}
        t = threading.Thread(target=self.load_image_worker, args=(real_norm_path, self._images[real_norm_path]))
        t.start()
        self._images[real_norm_path]['task'] = t
        logger.debug("  finished queue_image_read with: \"" + str(real_norm_path) + "\"")

    def make_available(self, requested):
        # logger.info('  ImageLibrary.make_available called by ' + inspect.stack()[1].function + '...')
        """
        SOMETHING TO LOOK AT:
        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.
        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        # logger.info('Making available ', str(sorted([str(s[-7:]) for s in requested])))
        already_loaded = set(self._images.keys())
        normalized_requested = set([self.pathkey(f) for f in requested])
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference(f)
        for f in need_to_load:
            if self.threaded_loading_enabled:
                self.queue_image_read(f)  # Using this will enable threaded reading behavior
            else:
                self.get_image_reference(f)  # Using this will force sequential reading behavior
        self.print_load_status()

    def remove_all_images(self):
        # logger.info("ImageLibrary is removing all images (called by " + inspect.stack()[1].function + ")...")
        keys = list(self._images.keys())
        for k in keys:
            self.remove_image_reference(k)
        self._images = {}

    def update(self):
        pass


def image_completed_loading(par):
    '''This is called only by SmartImageLibrary'''
    logger.info('\n' + 100 * '$' + '\n' + 100 * '$')
    logger.info("Got: " + str(par))
    logger.info("Image completed loading, check if showing and repaint as needed.")
    ## The following is needed to auto repaint, but it crashes instantly.
    ##alignem_swift.main_win.image_panel.refresh_all_images()
    logger.info('\n' + 100 * '$' + '\n' + 100 * '$')


def image_loader(real_norm_path, image_dict):
    '''Load images using psutil.virtual_memory()
    This is called only by SmartImageLibrary'''

    try:
        # Load the image
        logger.debug("  image_loader started with: \"" + str(real_norm_path) + "\"")
        m = psutil.virtual_memory() #0526
        logger.debug("   memory available before loading = " + str(m.available))

        image_dict['image'] = QPixmap(real_norm_path) # no class
        image_dict['loaded'] = True
        logger.debug("  image_loader finished for: \"" + str(real_norm_path) + "\"")
        logger.debug("  memory available after loading = " + str(m.available))
    except:
        logger.info("Got an exception in image_loader")


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
        ''''image_library.get_image_reference is called by: ZoomPanWidget.center_image, ZoomPanWidget.paintEvent'''
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
        if self.print_switch: logger.info("top of queue_image_read ( " + file_path + ")")
        real_norm_path = self.pathkey(file_path)
        self._images[real_norm_path] = {'image': None, 'loaded': False, 'loading': True, 'task': None}
        if self.print_switch: logger.info("submit with (" + real_norm_path + ", " + str(self._images[real_norm_path]) + ")")
        task_future = self.executors.submit(image_loader, real_norm_path, self._images[real_norm_path])
        # task_future.add_done_callback(image_completed_loading) #0701
        if self.print_switch: logger.info("  task_future: " + str(task_future))
        self._images[real_norm_path]['task'] = task_future

    def make_available(self, requested):
        """
        SOMETHING TO LOOK AT:

        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.

        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        logger.debug("make_available: " + str(sorted([str(s[-7:]) for s in requested])))
        already_loaded = set(self._images.keys())
        normalized_requested = set([self.pathkey(f) for f in requested])
        need_to_load = normalized_requested - already_loaded
        need_to_unload = already_loaded - normalized_requested
        for f in need_to_unload:
            self.remove_image_reference(f)
        for f in need_to_load:
            if self.threaded_loading_enabled:
                self.queue_image_read(f)  # Using this will enable threaded reading behavior
            else:
                self.get_image_reference(f)  # Using this will force sequential reading behavior

        logger.debug("Library has " + str(len(self._images.keys())) + " images")

    def update(self):
        cur_scale_key = cfg.project_data['data']['current_scale']
        cur_scale_val = get_scale_val(cur_scale_key)
        cur_layer_index = cfg.project_data['data']['current_layer']
        scale_keys = sorted(cfg.project_data['data']['scales'].keys())
        scale_vals = sorted(get_scale_val(scale_key) for scale_key in scale_keys)
        cur_stack = cfg.project_data['data']['scales'][cur_scale_key]['alignment_stack']
        layer_nums = range(len(cur_stack))
        amem = psutil.virtual_memory().available
        if self.print_switch: logger.info("Looking at: scale " + str(cur_scale_val) + " in " + str(scale_vals) + ", layer " + str(
            cur_layer_index) + " in " + str(layer_nums) +
              ", Available Memory = " + str(amem) + " out of " + str(self.initial_memory.available))

        try:
            stack = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['alignment_stack']
            layer = stack[cfg.project_data['data']['current_layer']]
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
