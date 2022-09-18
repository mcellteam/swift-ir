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
from src.helpers import print_exception

__all__ = ['ImageLibrary']

logger = logging.getLogger(__name__)

class ImageLibrary:
    """A class containing multiple images keyed by their file name."""

    def __init__(self):
        self._images = {}  # { image_key: { "task": task, "loading": bool, "loaded": bool, "image": image }
        self.threaded_loading_enabled = True

    def pathkey(self, file_path):
        if (file_path == None) or (file_path == ''):
            return None
        return os.path.abspath(os.path.normpath(file_path))

    def print_load_status(self):

        cfg.main_window.hud.post("  Library has " + str(len(self._images.keys())) + " images")
        cfg.main_window.hud.post("  Names:   " + str(sorted([str(s[-7:]) for s in self._images.keys()])))
        cfg.main_window.hud.post("  Loaded:  " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loaded']])))
        cfg.main_window.hud.post("  Loading: " + str(sorted([str(s[-7:]) for s in self._images.keys() if self._images[s]['loading']])))


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

    # def set_zarr_refs(self):
    #     for s in cfg.data.scales():
    #         dest = cfg.data.dest()
    #         path = os.path.join(dest, s + '.zarr')
    #         self.scaled_zarrs[s] = da.from_zarr(path, inline_array=True)
    #         self.scaled_zarrs[s] = np.moveaxis(self.scaled_zarrs[s], 0, 2)

    def preload_images(self, requested):
        # Preloads Images for All Roles

        # logger.critical('requested = %d' % requested)
        stack = cfg.data['data']['scales'][cfg.data.scale()]['alignment_stack']
        preload_imgs = set()
        rng = cfg.PRELOAD_RANGE

        for i in range(requested - rng, requested + rng):
            try:
                for role, local_image in stack[i]['images'].items():
                    if local_image['filename'] != None:
                        if len(local_image['filename']) > 0:
                            logger.debug('(i=%d) Adding This Image: %s' % (i,local_image['filename']))
                            preload_imgs.add(local_image['filename'])
            except IndexError:
                logger.warning('List Index Is Out Of Range!')
        self.make_available(preload_imgs)

    def preload_slices(self, requested):
        rng = range(requested - cfg.PRELOAD_RANGE, requested + cfg.PRELOAD_RANGE + 1)
        self.make_slices_available(rng)


    def get_image_reference(self, file_path):
        '''
        Called by:
        <--paintEvent

        '''
        logger.debug("Getting image reference, arg: %s" % file_path)
        # print_debug(50, "get_image_reference ( " + str(file_path) + " )")
        # self.print_load_status()
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
        '''

        center_image <-- Called By

        example arg: /Users/joelyancey/glanceEM_SWiFT/test_projects/'''
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
        logger.debug("  ImageLayer is removing image reference (called by " + inspect.stack()[1].function + ")...")
        image_ref = None
        if not (file_path is None):
            real_norm_path = self.pathkey(file_path)
            if real_norm_path in self._images:
                image_ref = self._images.pop(real_norm_path)['image']
        # This returned value may not be valid when multi-threading is implemented
        return image_ref

    def make_available(self, requested):
        """

        Called By: preload_images
        Calls: queue_image_read

        SOMETHING TO LOOK AT:
        Note that the threaded loading sometimes loads the same image multiple
        times. This may be due to an uncertainty about whether an image has been
        scheduled for loading or not.
        Right now, the current check is whether it is actually loaded before
        scheduling it to be loaded. However, a load may be in progress from an
        earlier request. This may cause images to be loaded multiple times.
        """

        logger.critical('\nrequested =\n %s' % str(requested))
        logger.debug('Making available %s' % str(sorted([str(s[-7:]) for s in requested])))
        already_loaded = set(self._images.keys())
        normalized_requested = set([self.pathkey(f) for f in requested])
        need_to_load = normalized_requested - already_loaded
        need_to_load.discard(None)
        need_to_unload = already_loaded - normalized_requested
        logger.critical('already_loaded = %s ' % str(already_loaded))
        logger.critical('need_to_load = %s ' % str(need_to_load))
        logger.critical('need_to_unload = %s ' % str(need_to_unload))

        '''
        already_loaded = set()
        need_to_load = {'/Users/joelyancey/glanceem_swift/test_projects/test7/scale_4/img_src/R34CA1-BS12.101.tif', ...
        need_to_unload = set()
        
        need_to_load = {
        '/Users/joelyancey/glanceem_swift/test_projects/3imgs/scale_4/img_src/R34CA1-BS12.101.tif', 
        '/Users/joelyancey/glanceem_swift/test_projects/3imgs/scale_4/img_src/R34CA1-BS12.103.tif', 
        '/Users/joelyancey/glanceem_swift/test_projects/3imgs/scale_4/img_src/R34CA1-BS12.102.tif', 
        '/Users/joelyancey/glanceem_swift/alignEM'
        }
        '''
        for f in need_to_unload:
            self.remove_image_reference(f)
        for f in need_to_load:
            logger.critical('need_to_load: %s' % str(need_to_load))
            if self.threaded_loading_enabled:
                self.queue_image_read(f)  # Using this will enable threaded reading behavior
            else:
                self.get_image_reference(f)  # Using this will force sequential reading behavior
        # self.print_load_status()


    def queue_image_read(self, file_path):
        '''
        Calls the Threading module (target=load_image_worker)

        Calls --> load_image_worker
        '''
        logger.info("Caller: %s" % inspect.stack()[1].function)
        logger.info('file_path = %s' % file_path)



        real_norm_path = self.pathkey(file_path)
        self._images[real_norm_path] = {'image': None, 'loaded': False, 'loading': True, 'task': None}
        t = threading.Thread(target=self.load_image_worker, args=(real_norm_path, self._images[real_norm_path]))
        t.start()
        self._images[real_norm_path]['task'] = t

        logger.debug("  finished queue_image_read with: \"" + str(real_norm_path) + "\"")

    # Load the image
    def load_image_worker(self, real_norm_path, image_dict):
    # def load_image_worker(self, image_dict):
        '''Target Process for Threaded Image Loader.'''
        logger.critical('!!! real_norm_path = %s' % real_norm_path)
        # real_norm_path
        # = /Users/joelyancey/glanceem_swift/test_projects/test_larger/scale_4/img_src/R34CA1-BS12.198.tif

        # logger.info("load_image_worker started with: %s" % str(real_norm_path))

        # np_data = zarr.load(path)
        # np_data = np.transpose(np_data, axes=[1, 2, 0])
        # zarr_data = da.from_zarr(path, chunks=(1, 512, 512))
        s = cfg.data.scale()
        image = self.scaled_zarrs[s][:, :, cfg.data.layer()] # SHOULD NOT BE GET_LAYER
        qimage = qimage2ndarray.array2qimage(np.asarray(image), True) #***
        # image_dict['image'] = QPixmap(real_norm_path) # no class  #orig                #key #0913
        image_dict['image'] = QPixmap.fromImage(qimage)
        image_dict['loaded'] = True
        image_dict['loading'] = False
        # logger.debug("load_image_worker finished for: %s" % str(real_norm_path))
        # self.print_load_status()

    def remove_all_images(self):
        logger.info("Called by %s" % inspect.stack()[1].function)
        keys = list(self._images.keys())
        for k in keys:
            self.remove_image_reference(k)
        self._images = {}

    #0827-
    # def update(self):
    #     logger.info('ImageLibrary wants to update but does not know how!')
    #     pass


def image_completed_loading(par):
    '''This is called only by SmartImageLibrary'''
    logger.debug('\n' + 100 * '$' + '\n' + 100 * '$')
    logger.debug("Got: " + str(par))
    logger.debug("Image completed loading, check if showing and repaint as needed.")
    ## The following is needed to auto repaint, but it crashes instantly.
    ##alignem_swift.main_win.image_panel.refresh_all_images()
    logger.debug('\n' + 100 * '$' + '\n' + 100 * '$')


def image_loader(real_norm_path, image_dict):
    '''Load images using psutil.virtual_memory()
    This is called only by SmartImageLibrary'''

    try:
        # Load the image
        logger.debug("  image_loader started with: \"" + str(real_norm_path) + "\"")
        m = psutil.virtual_memory() #0526
        logger.info("   memory available before loading = " + str(m.available))

        image_dict['image'] = QPixmap(real_norm_path) # no class
        image_dict['loaded'] = True


        logger.debug("  image_loader finished for: \"" + str(real_norm_path) + "\"")
        logger.info("  memory available after loading = " + str(m.available))
    except:
        logger.warning("Got an exception in image_loader")






