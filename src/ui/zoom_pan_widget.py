#!/usr/bin/env python3

import os
import sys
import logging
import inspect
import qtpy
from qtpy.QtGui import QPainter, QPen, QColor
from qtpy.QtWidgets import QWidget, QRubberBand
from qtpy.QtCore import Qt, QPointF, QRectF, QSize
from qtpy.QtWidgets import QSizePolicy

from qtpy.QtGui import QNativeGestureEvent

import src.config as cfg
from ..em_utils import get_num_imported_images
from ..em_utils import get_cur_layer
from ..em_utils import get_cur_scale_key
from ..em_utils import print_exception
from ..em_utils import is_dataset_scaled
from ..em_utils import get_cur_snr
from ..em_utils import are_images_imported
from ..em_utils import is_cur_scale_aligned
from ..em_utils import get_scale_val

'''
Deprecated .delta function

'''

__all__ = ['ZoomPanWidget']

logger = logging.getLogger(__name__)

class ZoomPanWidget(QWidget):
    """A widget to display a single annotated image with zooming and panning."""

    def __init__(self, role, parent=None):
        super(ZoomPanWidget, self).__init__(parent)
        self.role = role
        self.parent = None
        self.already_painting = False
        self.floatBased = False
        self.antialiased = False  # why
        self.wheel_index = 0
        self.scroll_factor = 1.25 #Critical
        self.zoom_scale = 1.0
        self.last_button = Qt.MouseButton.NoButton

        # self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) #0827-

        self.mdx = 0  # Mouse Down x (screen x of mouse down at start of drag)
        self.mdy = 0  # Mouse Down y (screen y of mouse down at start of drag)
        self.ldx = 0  # Last dx (fixed while dragging)
        self.ldy = 0  # Last dy (fixed while dragging)
        self.dx = 0  # Offset in x of the image
        self.dy = 0  # Offset in y of the image

        self.draw_border = False
        self.draw_annotations = True
        self.setAutoFillBackground(True)
        # self.setContentsMargins(10, 10, 10, 10) #0719-
        # self.border_color = QColor(100, 100, 100, 255)
        # self.setBackgroundRole(QPalette.Base)    #0610 removed
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) #0719
        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self) #0610 removed  #0701 activated
        self.need_to_center = 0

        self.setStyleSheet("""QToolTip { 
                                        background-color: #8ad4ff;
                                        /*color: white;*/
                                        color: #000000;
                                        border: #8ad4ff solid 1px;
                                        }""")

        # self.setToolTip('GlanceEM_SWiFT')  # tooltip #settooltip
        # tooltip.setTargetWidget(btn)
        #
        # self.lb = QLabel(self)
        # self.pixmap = QPixmap("{sims.png}")
        # self.height_label = 100
        # self.lb.resize(self.width(), self.height_label)
        # self.lb.setPixmap(self.pixmap.scaled(self.lb.size(), src.IgnoreAspectRatio))
        # self.show()

        # focus

        #0605 following 6 lines were removed
    #     QApplication.instance().focusChanged.connect(self.on_focusChanged)
    #
    def on_focusChanged(self):
        fwidget = QApplication.focusWidget()
        if fwidget is not None:
            logger.info("focus widget name = ", fwidget.objectName())

    def get_settings(self):
        settings_dict = {}
        for key in ["floatBased", "antialiased", "wheel_index", "scroll_factor", "zoom_scale", "last_button", "mdx",
                    "mdy", "ldx", "ldy", "dx", "dy", "draw_border", "draw_annotations"]:
            settings_dict[key] = self.__dict__[key]
        return settings_dict

    def set_settings(self, settings_dict):
        for key in settings_dict.keys():
            self.__dict__[key] = settings_dict[key]

    def set_parent(self, parent):
        self.parent = parent

    def update_siblings(self):
        logger.info('Caller: ' + inspect.stack()[1].function)
        # This will cause the normal "update_self" function to be called on each sibling
        self.parent.update_multi_self(exclude=[self])

    def update_zpa_self(self):
        '''Update Annotation Boolean'''
        # logger.info('Caller: ' + inspect.stack()[1].function)
        # Call the super "update" function for this panel's QWidget (this "self")
        self.draw_annotations = self.parent.draw_annotations
        # if self.parent != None:
        #     # self.draw_border = self.parent.draw_border #border #0520
        #     self.draw_annotations = self.parent.draw_annotations

        super(ZoomPanWidget, self).update() #Critical

    def show_actual_size(self):
        self.zoom_scale = 1.0
        self.ldx = 0
        self.ldy = 0
        self.wheel_index = 0
        if qtpy.QT5:    self.zoom_to_wheel_at(0, 0) #pyside2
        elif qtpy.QT6:  self.zoom_to_wheel_at(QPointF(0.0, 0.0))  #pyside6

    # ZoomPanWidget.center_image called once for each role/panel
    def center_image(self, all_images_in_stack=True):
        try:
            s = cfg.project_data['data']['current_scale']
            l = cfg.project_data['data']['current_layer']
            if len(cfg.project_data['data']['scales'][s]['alignment_stack']) > 0:

                image_dict = cfg.project_data['data']['scales'][s]['alignment_stack'][l]['images']
                if self.role in image_dict.keys():
                    ann_image = image_dict[self.role]
                    img_text = ann_image['filename']
                    '''Call To cfg.image_library'''
                    pixmap = cfg.image_library.get_image_reference(img_text) #  <class 'PySide6.QtGui.QPixmap'>
                    self.image_w, self.image_h = pixmap.width(), pixmap.height()
                    if pixmap is None:
                        logger.warning("'pixmap' is None")
                    if (pixmap != None) or all_images_in_stack:
                        img_w, img_h = 0, 0
                        if pixmap != None:
                            img_w, img_h = pixmap.width(), pixmap.height()
                        win_w, win_h = self.width(), self.height()

                        if all_images_in_stack:
                            # Search through all images in this stack to find bounds
                            stack = cfg.project_data['data']['scales'][s]['alignment_stack']
                            for layer in stack:
                                if 'images' in layer.keys():
                                    if self.role in layer['images'].keys():
                                        other_pixmap = cfg.image_library.get_image_reference_if_loaded(layer['images'][self.role]['filename'])
                                        if other_pixmap != None:
                                            '''TODO This will need to be rafactored for non-square images'''
                                            other_w = other_pixmap.width()
                                            other_h = other_pixmap.height()
                                            img_w = max(img_w, other_w)
                                            img_h = max(img_h, other_h)

                        if (img_w <= 0) or (img_h <= 0) or (win_w <= 0) or (win_h <= 0):  # Zero or negative dimensions might lock up?
                            self.need_to_center = 1
                            logger.warning("Cannot center image for role %s" % self.role)

                        else:
                            # Start with the image at a zoom of 1 (natural size) and with the mouse wheel centered (at 0)
                            self.zoom_scale = 1.0
                            self.ldx = 0
                            self.ldy = 0
                            self.wheel_index = 0

                            # Enlarge the image (scaling up) while it is within the size of the window
                            while (self.win_x(img_w) <= win_w) and (self.win_y(img_h) <= win_h):
                                logger.debug("Enlarging image to fit in center.")
                                if qtpy.QT5:    self.zoom_to_wheel_at(0, 0)  # pyside2
                                elif qtpy.QT6:  self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
                                # self.wheel_index += 1
                                self.wheel_index += 0.5
                                logger.debug("  Wheel index = " + str(self.wheel_index) + " while enlarging")
                                logger.debug("    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(
                                                win_w) + "x" + str(win_h))
                                # logger.info("    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                if abs(self.wheel_index) > 100:
                                    logger.warning("Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index))
                                    break

                            # Shrink the image (scaling down) while it is larger than the size of the window
                            while (self.win_x(img_w) > win_w) or (self.win_y(img_h) > win_h):

                                # logger.info("\nShrinking image to fit in center.")
                                # logger.info("type(img_w) = %s" % type(img_w))
                                # logger.info("type(self.win_x) = %s" % type(self.win_x))
                                # logger.info("type(self.win_x(img_w)) = %s" % str(type(self.win_x(img_w))))
                                # logger.info("self.win_x(img_w) = %s" % str(self.win_x(img_w)))
                                if qtpy.QT5:    self.zoom_to_wheel_at(0, 0)  # pyside2
                                elif qtpy.QT6:  self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
                                # self.wheel_index += -1
                                self.wheel_index += -0.5
                                # logger.info("  Wheel index = " + str(self.wheel_index) + " while shrinking")
                                # logger.info("    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(win_w) + "x" + str(win_h))
                                # logger.info("    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                if abs(self.wheel_index) > 100:
                                    logger.warning("Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index))
                                    break

                            # # Adjust the offsets to center
                            extra_x = win_w - self.win_x(img_w)
                            extra_y = win_h - self.win_y(img_h)
                            # # Bias the y value downward to make room for text at top
                            # extra_y = 1.7 * extra_y #orig
                            # extra_y = 2.2 * extra_y    #0827-
                            self.ldx = (extra_x / 2) / self.zoom_scale    #0827-
                            self.ldy = (extra_y / 2) / self.zoom_scale    #0827-
        except:
            logger.warning('Failed to Center Images')
            print_exception()

        self.set_tooltips()

    def set_tooltips(self):
        if are_images_imported():
            s = cfg.project_data['data']['current_scale']
            l = cfg.project_data['data']['current_layer']
            # n_images = get_num_imported_images()
            role_dict = {'ref': 'Reference Image', 'base': 'Current Image', 'aligned': 'Alignment'}
            role_str = role_dict[self.role]
            try:
                dim_str = '%sx%spx' % (self.image_w, self.image_h)
            except:
                dim_str = ''
            scale_str = 'Scale %d' % get_scale_val(s)
            snr_str = str(get_cur_snr())
            if self.role == 'aligned':
                if is_cur_scale_aligned():
                    self.setToolTip('%s\n%s [%s]\n%s' % (role_str, scale_str, dim_str, snr_str))
            else:
                self.setToolTip('%s\n%s [%s]' % (role_str, scale_str, dim_str))
        else:
            self.setToolTip('No Image')


    def win_x(self, image_x):
        '''Note this is being called 4 times each time
        17:16:20 CRITICAL [zoom_pan_widget.win_x:247] (center_image) win_x is returning 1342.17728
        17:16:20 CRITICAL [zoom_pan_widget.win_x:248] self.zoom_scale = 0.32768
        17:16:20 CRITICAL [zoom_pan_widget.win_x:249] self.ldx = 0.0
        17:16:20 CRITICAL [zoom_pan_widget.win_x:250] self.dx = 0

        17:16:20 CRITICAL [zoom_pan_widget.win_x:247] (center_image) win_x is returning 1073.741824
        17:16:20 CRITICAL [zoom_pan_widget.win_x:248] self.zoom_scale = 0.262144
        17:16:20 CRITICAL [zoom_pan_widget.win_x:249] self.ldx = 0.0
        17:16:20 CRITICAL [zoom_pan_widget.win_x:250] self.dx = 0

        17:16:20 CRITICAL [zoom_pan_widget.win_x:247] (center_image) win_x is returning 858.9934592
        17:16:20 CRITICAL [zoom_pan_widget.win_x:248] self.zoom_scale = 0.2097152
        17:16:20 CRITICAL [zoom_pan_widget.win_x:249] self.ldx = 0.0
        17:16:20 CRITICAL [zoom_pan_widget.win_x:250] self.dx = 0
        '''

        logger.debug('(%s) win_x is returning %s' % (inspect.stack()[1].function, str(self.zoom_scale * (image_x + self.ldx + self.dx))))
        logger.debug('self.zoom_scale = %s' % str(self.zoom_scale))
        logger.debug('self.ldx = %s' % str(self.ldx))
        logger.debug('self.dx = %s' % str(self.dx))

        v = self.zoom_scale * (image_x + self.ldx + self.dx)
        # return self.zoom_scale * (image_x + self.ldx + self.dx)
        # return image_x
        # zoom_scale = self.zoom_scale
        return v

    def image_x(self, win_x):
        img_x = (win_x / self.zoom_scale) - self.ldx
        # logger.critical('(%s) image_x is returning %s' % inspect.stack()[1].function, str(img_x))
        return img_x

    def win_y(self, image_y):
        v = self.zoom_scale * (image_y + self.ldy + self.dy)
        return v

    def image_y(self, win_y):
        img_y = (win_y / self.zoom_scale) - self.ldy
        return img_y

    def dump(self):
        logger.info("wheel = %s" % str(self.wheel_index))
        logger.info("zoom  = %s" % str(self.zoom_scale))
        logger.info("ldx = %s, ldy = %s" % (str(self.ldx), str(self.ldy)))
        logger.info("mdx = %s, mdy = %s" % (str(self.mdx), str(self.mdy)))
        logger.info(" dx = %s,  dy = %s" % (str(self.dx), str(self.dy)))

    def setFloatBased(self, float_based):
        self.floatBased = float_based
        self.update_zpa_self()

    def setAntialiased(self, antialiased):
        self.antialiased = antialiased
        self.update_zpa_self()


    # def minimumSizeHint(self):
    #     return QSize(50, 50)
    #
    # def sizeHint(self):
    #     return QSize(180, 180)


    def mouse_down_callback(self, role, screen_coords, image_coords, button):
        # global match_pt_mode
        # if match_pt_mode.get_value():
        if cfg.main_window.match_point_mode == True:
            logger.info("Adding a match point for role \"" + str(role) + "\" at " + str(
                screen_coords) + " == " + str(image_coords))
            stack = cfg.project_data['data']['scales'][cfg.project_data['data']['current_scale']]['alignment_stack']
            layer = stack[cfg.project_data['data']['current_layer']]

            if not 'metadata' in layer['images'][role]:
                layer['images'][role]['metadata'] = {}

            metadata = layer['images'][role]['metadata']

            if not 'match_points' in metadata:
                metadata['match_points'] = []
            match_point_data = [c for c in image_coords]
            metadata['match_points'].append(match_point_data)

            if not 'annotations' in metadata:
                metadata['annotations'] = []
            '''
            # Use default colors when commented, so there are no colors in the JSON
            if not 'colors' in metadata:
                metadata['colors'] = [ [ 255, 0, 0 ], [ 0, 255, 0 ], [ 0, 0, 255 ], [ 255, 255, 0 ], [ 255, 0, 255 ], [ 0, 255, 255 ] ]
            '''

            match_point_data = [m for m in match_point_data]

            color_index = len(metadata['annotations'])
            match_point_data.append(color_index)

            metadata['annotations'].append("circle(%f,%f,10,%d)" % tuple(match_point_data))
            for ann in metadata['annotations']:
                logger.info("   Annotation: " + str(ann))
            return (True)  # Lets the framework know that the click has been handled
        else:
            logger.info("Do Normal Processing")
            return (False)  # Lets the framework know that the click has not been handled

    #0821
    # def event(self, e):
    #     if isinstance(e, QNativeGestureEvent):
    #         print(e.gestureType(), e.pos(), e.value())
    #         if event.delta() > 0:
    #             factor = 1.25
    #             self._zoom += 1
    #         else:
    #             factor = 0.8
    #             self._zoom -= 1
    #         if self._zoom > 0:
    #             self.scale(factor, factor)
    #         elif self._zoom == 0:
    #             self.fitInView()
    #         else:
    #             self._zoom = 0


    def mousePressEvent(self, event):
        print('mousePressEvent:')
        ex = event.x()
        ey = event.y()
        self.last_button = event.button()
        if event.button() == Qt.MouseButton.RightButton:
            # Reset the pan and zoom
            self.dx = self.mdx = self.ldx = 0
            self.dy = self.mdy = self.ldy = 0
            self.wheel_index = 0
            self.zoom_scale = 1.0
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.dump()
        else:
            # Set the Mouse Down position to be the screen location of the mouse
            self.mdx = ex
            self.mdy = ey

        self.update_zpa_self()


    def mouseMoveEvent(self, event):
        if self.last_button == Qt.MouseButton.LeftButton:
            self.dx = (event.x() - self.mdx) / self.zoom_scale
            self.dy = (event.y() - self.mdy) / self.zoom_scale
        self.update_zpa_self()


    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.ldx += self.dx
            self.ldy += self.dy
            self.dx, self.dy = 0, 0
        self.update_zpa_self()

    def mouseDoubleClickEvent(self, event):
        pass


    def zoom_to_wheel_at(self, pos, pos_y=None):
        ''' #ThreeCalls
        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:417] self.scroll_factor = 1.25
        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:418] self.wheel_index = -9
        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:422] --> old_scale=0.16777216, new_scale=0.134217728

        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:417] self.scroll_factor = 1.25
        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:418] self.wheel_index = -10
        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:422] --> old_scale=0.134217728, new_scale=0.1073741824

        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:417] self.scroll_factor = 1.25
        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:418] self.wheel_index = -11
        17:54:34 CRITICAL [zoom_pan_widget.zoom_to_wheel_at:422] --> old_scale=0.1073741824, new_scale=0.08589934592
        '''

        # logger.critical('self.scroll_factor = %s' % str(self.scroll_factor))
        # logger.critical('self.wheel_index = %s' % str(self.wheel_index))
        old_scale = self.zoom_scale
        new_scale = self.zoom_scale = pow(self.scroll_factor, self.wheel_index) #Critical

        # logger.critical('--> old_scale=%s, new_scale=%s' % (old_scale,new_scale))
        if qtpy.QT5:
            #Original
            logger.debug('zoom_to_wheel_at (Qt5):')
            self.ldx = self.ldx + (pos/new_scale) - (pos/old_scale)
            self.ldy = self.ldy + (pos_y/new_scale) - (pos_y/old_scale)
        elif qtpy.QT6:
            logger.debug('zoom_to_wheel_at (Qt6):')
            self.ldx = self.ldx + (pos.x() / new_scale) - (pos.x() / old_scale)
            self.ldy = self.ldy + (pos.y() / new_scale) - (pos.y() / old_scale)
        # logger.info('self.ldx: %s' % str(self.ldx))
        # logger.info('self.ldy: %s' % str(self.ldy))


    def change_layer(self, layer_delta):
        """This function loads the next or previous layer"""
        cfg.main_window.set_status('Loading...')
        cfg.main_window.jump_to_worst_ticker = 1
        cfg.main_window.jump_to_best_ticker = 1
        if is_dataset_scaled():
            cfg.main_window.read_gui_update_project_data()
        n_imgs = get_num_imported_images()
        scale = get_cur_scale_key()
        leaving = get_cur_layer()
        requested = leaving + layer_delta
        rng = cfg.PRELOAD_RANGE
        if requested in range(n_imgs): pass
        elif requested < 0: logger.info('Cant layer down any further!'); cfg.main_window.set_idle(); return
        elif requested > n_imgs - 1: logger.info('Cant layer up any further!'); cfg.main_window.set_idle(); return
        logger.info("Changing to layer %s" % requested)
        stack = cfg.project_data['data']['scales'][scale]['alignment_stack']
        cfg.project_data['data']['current_layer'] = requested
        preload_imgs = set()
        for i in range(requested - rng, requested + rng):
            try:
                for role, local_image in stack[i]['images'].items():
                    if local_image['filename'] != None:
                        preload_imgs.add(local_image['filename'])
            except:
                # print_exception()
                logger.warning('Failed to load image for role %s' % self.role)
        cfg.image_library.make_available(preload_imgs)
        if is_dataset_scaled():
            cfg.main_window.read_project_data_update_gui()
        self.update_zpa_self()
        self.update_siblings() # <- change all layers
        # hack to fix bug when proj closed on layer 0 (ref not loaded)
        if self.need_to_center == 1:
            cfg.main_window.center_all_images()
            self.need_to_center = 0
        self.set_tooltips()
        cfg.main_window.set_idle()

    def wheelEvent(self, event):
        logger.debug("wheelEvent:")
        """
        AttributeError: 'PySide6.QtGui.QWheelEvent' object has no attribute 'delta'

        PySide6 error with scroll. PySide6 has angleDelta() and pixelDelta() - in place of delta()

        I think delta() is comparable to angleDelta()

        PySide2.QtGui.QWheelEvent.delta() has been deprecated, use pixelDelta() or angleDelta() instead
        PySide2.QtGui.QWheelEvent.delta() returns 'int'

        PySide6.QtGui.QWheelEvent.angleDelta() returns PySide6.QtCore.QPoint
        PySide6.QtGui.QWheelEvent.pixelDelta() returns PySide6.QtCore.QPoint

        PySide6 Ref: https://doc.qt.io/qtforpython/PySide6/QtGui/QWheelEvent.html
        Wheel events are sent to the widget under the mouse cursor, but if that widget does not handle the event they
        are sent to the focus widget. Wheel events are generated for both mouse wheels and trackpad scroll gestures. T
        There are two ways to read the wheel event delta:
          angleDelta() returns the deltas in wheel degrees (wheel rotation angle)
          pixelDelta() returns the deltas in screen pixels, (scrolling distance) and is available on platforms that have high-resolution trackpads, such as macOS
        PySide6.QtCore.QPoint


        other QWheelEvent notes:
          position() and globalPosition() return the mouse cursor’s location at the time of the event
          You should call ignore() if you do not handle the wheel event; this ensures that it will be sent to the parent widget
          The setEnabled() function can be used to enable or disable mouse and keyboard events for a widget.

        # Ref on resolving deprecation issue:
        https://stackoverflow.com/questions/66268136/how-to-replace-the-deprecated-function-qwheeleventdelta-in-the-zoom-in-z
        # zoom: want use angleDelta().y() for vertical scrolling

        """
        '''refer to QWheelEvent class documentation'''

        kmods = event.modifiers()
        '''scroll w/ shift key     :  src.ShiftModifier
           scroll w/out shift key  :  src.NoModifier     '''
        logger.info('kmods = %s' % str(kmods))

        if qtpy.QT5:
            '''Original Code, Modified'''
            if ( int(kmods) & int(Qt.ShiftModifier)) == 0:
                # Unshifted Scroll Wheel moves through layers
                # layer_delta = int(event.delta()/120) # Delta Is Deprecated Use pixelDelta() or angleDelta()
                layer_delta = int(event.angleDelta().y()/120) # Delta Is Deprecated Use pixelDelta() or angleDelta()
                self.change_layer ( layer_delta )
            # elif (int(kmods) & int(Qt.ControlModifier)) == 0:
            #     layer_delta = int(event.angleDelta().y() / 120)  # Delta Is Deprecated Use pixelDelta() or angleDelta()
            #     self.change_layer(layer_delta)
            else:
                # Shifted Scroll Wheel zooms
                # self.wheel_index += event.delta()/120 # Delta Is Deprecated Use pixelDelta() or angleDelta()
                self.wheel_index += event.angleDelta().y()/120 # Delta Is Deprecated Use pixelDelta() or angleDelta()
                self.zoom_to_wheel_at(event.x(), event.y())
        else:
            if kmods == Qt.NoModifier:
                # Unshifted Scroll Wheel moves through layers

                # if qtpy.QT5 == True:
                #     layer_delta = int(event.delta()/120)    #pyside2
                # else:
                #     layer_delta = event.angleDelta().y()  # 0615 #0719

                layer_delta = event.angleDelta().y()
                self.change_layer(layer_delta)

                # Ref: https://stackoverflow.com/questions/35508711/how-to-enable-pan-and-zoom-in-a-qgraphicsview
                # _zoom is equivalent to wheel_index
                # if event.angleDelta().y() > 0:
                #     factor = 1.25
                #     self.wheel_index += 1
                # else:
                #     factor = 0.8
                #     self.wheel_index -= 1
                # if self.wheel_index > 0:
                #     self.scale(factor, factor)
                # elif self.wheel_index == 0:
                #     self.fitInView()
                # else:
                #     self.wheel_index = 0

        self.update_zpa_self() #Critical

    def paintEvent(self, event):
        # if self.already_painting:
        #     logger.warning('Painter was already painting!')
        #     return
        # self.already_painting = True

        s = cfg.project_data['data']['current_scale']
        l = cfg.project_data['data']['current_layer']
        # img_text = None
        if self.role == 'aligned':
            img_text = 'Unaligned'
        else:
            img_text = 'No Image Loaded'

        has_alignment_stack = True if len(cfg.project_data['data']['scales'][s]['alignment_stack']) > 0 else False
        try:
            painter = QPainter(self)
            # s = cfg.project_data['data']['current_scale']
            # l = cfg.project_data['data']['current_layer']
            role_text = str(self.role) + " [" + str(s) + "]" + " [" + str(l) + "]"
            if len(cfg.project_data['data']['scales'][s]['alignment_stack']) > 0: #debug #tag # previously uncommented
                image_dict = cfg.project_data['data']['scales'][s]['alignment_stack'][l]['images']
                is_skipped = cfg.project_data['data']['scales'][s]['alignment_stack'][l]['skip']
                if self.role in image_dict.keys():
                    ann_image = image_dict[self.role]
                    '''Get Image Reference From Library'''
                    pixmap = cfg.image_library.get_image_reference(ann_image['filename'])
                    self.image_w, self.image_h = pixmap.width(), pixmap.height()

                    img_text = ann_image['filename']
                    painter.scale(self.zoom_scale, self.zoom_scale) #scale painter to draw image as the background
                    if pixmap != None:
                        if self.draw_border:
                            pass
                            # Draw an optional border around the image
                            # painter.setPen(QPen(QColor(255, 255, 255, 255), 4))
                            # painter.drawRect(
                            #     QRectF(self.ldx + self.dx, self.ldy + self.dy, pixmap.width(), pixmap.height()))
                        # Draw the pixmap itself on top of the border to ensure every pixel is shown
                        # if (not is_skipped) or self.role == 'base':
                        '''Draw Image'''
                        painter.drawPixmap(QPointF(self.ldx + self.dx, self.ldy + self.dy), pixmap)

                        # Draw any items that should scale with the image

                    # Rescale painter to draw at screen resolution
                    zoom_scale = self.zoom_scale
                    painter.scale(1.0 / zoom_scale, 1.0 / zoom_scale)
                    # Draw the borders of the viewport for each panel to separate panels
                    # painter.setPen(QPen(self.border_color, 4)) #0523
                    # painter.drawRect(painter.viewport()) #0523

                    if self.draw_annotations and (pixmap != None):
                        if (pixmap.width() > 0) or (pixmap.height() > 0):
                            painter.setPen(QPen(QColor(128, 255, 128, 255), 5))
                            painter.drawText(painter.viewport().width() - 100, 40,"%dx%d" % (pixmap.width(), pixmap.height()))

                    if self.draw_annotations and 'metadata' in ann_image:
                        colors = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 255], [0, 255, 255]]
                        if 'colors' in ann_image['metadata']:
                            colors = ann_image['metadata']['colors']
                        if 'annotations' in ann_image['metadata']:
                            # Draw the application-specific annotations from the metadata
                            color_index = 0
                            ann_list = ann_image['metadata']['annotations']
                            for ann in ann_list:
                                logger.debug("Drawing " + ann)
                                cmd = ann[:ann.find('(')].strip().lower()
                                pars = [float(n.strip()) for n in ann[ann.find('(') + 1: -1].split(',')]
                                logger.debug("Command: " + cmd + " with pars: " + str(pars))
                                if len(pars) >= 4:
                                    color_index = int(pars[3])
                                else:
                                    color_index = 0

                                color_to_use = colors[color_index % len(colors)]
                                painter.setPen(QPen(QColor(*color_to_use), 5))
                                x, y, r = 0, 0, 0
                                if cmd in ['circle', 'square']:
                                    x = self.win_x(pars[0])
                                    y = self.win_y(pars[1])
                                    r = pars[2]
                                if cmd == 'circle':
                                    painter.drawEllipse(x - r, y - r, r * 2, r * 2)
                                if cmd == 'square':
                                    painter.drawRect(QRectF(x - r, y - r, r * 2, r * 2))
                                if cmd == 'skipped':
                                    # color_to_use = colors[color_index+1%len(colors)]
                                    color_to_use = [255, 50, 50]
                                    painter.setPen(QPen(QColor(*color_to_use), 5))
                                    # painter.drawEllipse ( x-(r*2), y-(r*2), r*4, r*4 )
                                    painter.drawLine(0, 0, painter.viewport().width(),
                                                     painter.viewport().height())
                                    painter.drawLine(0, painter.viewport().height(), painter.viewport().width(),
                                                     0)
                                color_index += 1

                    if is_skipped:
                        if self.role == 'base':
                            self.center_image() #0503 I think this helps
                            red_color = [255, 50, 50]
                            painter.setPen(QPen(QColor(*red_color), 3))
                            factor = 6
                            width = painter.viewport().width() / factor
                            height = painter.viewport().height() / factor
                            # x1a, y1a, x2a, y2a = 0, 0, width, height
                            # x1b, y1b, x2b, y2b = 0, width, height, 0
                            x1a, y1a, x2a, y2a = 0, painter.viewport().height(), width, painter.viewport().height() - height
                            x1b, y1b, x2b, y2b = 0, painter.viewport().height() - height, width, painter.viewport().height()
                            # x1a, y1a, x2a, y2a = 0, 0, width, height
                            # x1b, y1b, x2b, y2b = 0, width, height, 0
                            painter.drawLine(x1a, y1a, x2a, y2a)
                            painter.drawLine(x1b, y1b, x2b, y2b)
                            # painter.setOpacity(0.5)
                            # painter.setOpacity(0)
                            # painter.setBrush(Qt.black)  # Background
                            # painter.drawRect(x1a, y1a, x2a, y2a)
                            # painter.setPen(QPen(Qt.red))  # Border

                        # if self.role == 'base':
                        #     width = painter.viewport().width() / factor
                        #     height = painter.viewport().height() / factor
                        #     x1b, y1b, x2b, y2b = 0, painter.viewport().height() - height, width, painter.viewport().height()
                        #     painter.drawText(x1b, y1b, 'SKIP')


                        painter.setOpacity(0.5)
                        painter.setBrush(Qt.black) # Entire MultiImagePanel Background
                        painter.setPen(QPen(Qt.black)) # Border
                        # rect = QRect(0, 0, painter.viewport().width(), painter.viewport().height())
                        painter.drawRect(painter.viewport())

                        # painter.fillRect(rect, QBrush(QColor(128, 128, 255, 128)))

            if self.draw_annotations:
                if (not has_alignment_stack) and ((self.role=='aligned') or (self.role=='base')):
                        pass
                elif not cfg.IMAGES_IMPORTED:
                    pass


                else:
                    # if len(cfg.project_data['data']['scales'][s]['alignment_stack']) == 0:
                    # if (not is_skipped) or (self.role=='base'):
                    #     if self.role=='ref':
                    #
                    painter.setOpacity(1)
                    painter.setPen(QPen(QColor(255, 100, 100, 255), 5))
                    painter.drawText(10, 20, role_text)                   # Draw the role
                    painter.setPen(QPen(QColor(100, 100, 255, 255), 5))
                    painter.drawText(10, 40, os.path.split(img_text)[1])  # Draw the image name
                    scale = cfg.project_data['data']['scales'][s]
                    if len(scale['alignment_stack']) > 0:
                        layer = scale['alignment_stack'][l]
                        method_results = layer['align_to_ref_method']['method_results']
                        if 'snr_report' in method_results:
                            if method_results['snr_report'] != None:
                                painter.setPen(QPen(QColor(255, 255, 255, 255), 5))
                                midw = painter.viewport().width() / 3
                                painter.drawText(midw, 20, method_results['snr_report'])

            painter.end()
            del painter
            # self.already_painting = False
        except:
            print_exception()
            logger.warning('Something Went Wrong During Paint Event')
            pass

