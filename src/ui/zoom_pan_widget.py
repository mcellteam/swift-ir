#!/usr/bin/env python3

import os
import sys
import logging
import inspect
from qtpy.QtGui import QPainter, QPen, QColor
from qtpy.QtWidgets import QWidget, QRubberBand
from qtpy.QtCore import Qt, QPointF, QRectF
from qtpy.QtWidgets import QSizePolicy

from qtpy.QtGui import QNativeGestureEvent

import src.config as cfg
from ..em_utils import get_num_imported_images
from ..em_utils import get_cur_layer
from ..em_utils import get_cur_scale_key
from ..em_utils import print_exception
from ..em_utils import is_dataset_scaled
from ..em_utils import get_cur_snr


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
        self.scroll_factor = 1.25
        self.zoom_scale = 1.0
        self.last_button = Qt.MouseButton.NoButton

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

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
    # def on_focusChanged(self):
    #     fwidget = QApplication.focusWidget()
    #     if fwidget is not None:
    #         logger.info("focus widget name = ", fwidget.objectName())

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
        # This will cause the normal "update_self" function to be called on each sibling
        print_debug(30, "Update_siblings called, calling siblings.update_self")
        # if type(self.parent) == MultiImagePanel:  #0712 - had to remove circular reference
        self.parent.update_multi_self(exclude=[self])

    def update_zpa_self(self):
        logger.debug('Updating zpa self | Caller: ' + inspect.stack()[1].function + ' |  ZoomPanWidget.update_zpa_self...')
        # Call the super "update" function for this panel's QWidget (this "self")
        if self.parent != None:
            # self.draw_border = self.parent.draw_border #border #0520
            self.draw_annotations = self.parent.draw_annotations
        super(ZoomPanWidget, self).update()

        #04-04 #maybe better at the end of change_layer?
        scale_dict = {'scale_'}
        role_dict = {'ref': 'Reference Image', 'base': 'Work Image', 'aligned': 'Aligned Image'}
        if get_cur_snr() is None:
            self.setToolTip('%s\n%s\n%s' % (role_dict[self.role],
                                            str('Scale '+get_cur_scale_key()[-1]),
                                            'Unaligned' ))
        else:
            self.setToolTip('%s\n%s\n%s' % (str(role_dict[self.role]),
                                            'Scale '+get_cur_scale_key()[-1],
                                            str(get_cur_snr())))

    def show_actual_size(self):
        logger.debug("ZoomPanWidget.show_actual_size:")
        self.zoom_scale = 1.0
        self.ldx = 0
        self.ldy = 0
        self.wheel_index = 0
        # if cfg.USES_QT5:
        #     self.zoom_to_wheel_at ( 0, 0 ) #pyside2 #0613 removed
        # else:
        self.zoom_to_wheel_at(QPointF(0.0, 0.0))  #pyside6

    # ZoomPanWidget.center_image called once for each role/panel
    def center_image(self, all_images_in_stack=True):
        logger.debug("ZoomPanWidget.center_image | called by " + inspect.stack()[1].function)
        try:
            if cfg.project_data != None:
                # s = get_cur_scale_key()
                s = cfg.project_data['data']['current_scale']
                l = cfg.project_data['data']['current_layer']

                if len(cfg.project_data['data']['scales']) > 0:
                    #logger.info("s = ", s) #0406
                    # if len(cfg.project_data['data']['scales'][s]['alignment_stack']) > 0: #0509
                    if len(cfg.project_data['data']['scales'][s]['alignment_stack']):

                        image_dict = cfg.project_data['data']['scales'][s]['alignment_stack'][l]['images']
                        if self.role in image_dict.keys():
                            # logger.info("current role: ", self.role)
                            ann_image = image_dict[self.role] # <class 'dict'>
                            '''CALL TO cfg.image_library'''
                            img_text = ann_image['filename']
                            pixmap = cfg.image_library.get_image_reference(img_text) #  <class 'PySide6.QtGui.QPixmap'>


                            if pixmap is None: logger.warning("'pixmap' is set to None")
                            if (pixmap != None) or all_images_in_stack:
                                img_w = 0
                                img_h = 0
                                if pixmap != None:
                                    img_w = pixmap.width()
                                    img_h = pixmap.height()
                                win_w = self.width()
                                win_h = self.height()
                                # logger.info("win_w = %d, win_h = %d" % (win_w, win_h))

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
                                    logger.warning("Cannot center image for role %s. Called by %s" % (
                                        self.role, inspect.stack()[1].function))

                                else:
                                    # Start with the image at a zoom of 1 (natural size) and with the mouse wheel centered (at 0)
                                    self.zoom_scale = 1.0
                                    self.ldx = 0
                                    self.ldy = 0
                                    self.wheel_index = 0
                                    # self.zoom_to_wheel_at ( 0, 0 )

                                    # Enlarge the image (scaling up) while it is within the size of the window
                                    while (self.win_x(img_w) <= win_w) and (self.win_y(img_h) <= win_h):
                                        print_debug(70, "Enlarging image to fit in center.")
                                        # self.zoom_to_wheel_at ( 0, 0 ) #pyside2
                                        self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
                                        self.wheel_index += 1
                                        print_debug(80, "  Wheel index = " + str(self.wheel_index) + " while enlarging")
                                        print_debug(80,
                                                    "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(
                                                        win_w) + "x" + str(win_h))
                                        print_debug(80, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                        if abs(self.wheel_index) > 100:
                                            print_debug(-1, "Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index))
                                            break

                                    # Shrink the image (scaling down) while it is larger than the size of the window
                                    while (self.win_x(img_w) > win_w) or (self.win_y(img_h) > win_h):
                                        print_debug(70, "Shrinking image to fit in center.")
                                        # self.zoom_to_wheel_at ( 0, 0 ) #pyside2
                                        self.zoom_to_wheel_at(QPointF(0.0, 0.0))  # pyside6
                                        self.wheel_index += -1
                                        print_debug(80, "  Wheel index = " + str(self.wheel_index) + " while shrinking")
                                        print_debug(80,
                                                    "    Image is " + str(img_w) + "x" + str(img_h) + ", Window is " + str(
                                                        win_w) + "x" + str(win_h))
                                        print_debug(80, "    self.win_x(img_w) = " + str(self.win_x(img_w)) + ", self.win_y(img_h) = " + str(self.win_y(img_h)))
                                        if abs(self.wheel_index) > 100:
                                            print_debug(-1, "Magnitude of Wheel index > 100, wheel_index = " + str(self.wheel_index))
                                            break

                                    # Adjust the offsets to center
                                    extra_x = win_w - self.win_x(img_w)
                                    extra_y = win_h - self.win_y(img_h)

                                    # Bias the y value downward to make room for text at top
                                    # extra_y = 1.7 * extra_y #orig
                                    extra_y = 2.2 * extra_y
                                    self.ldx = (extra_x / 2) / self.zoom_scale
                                    self.ldy = (extra_y / 2) / self.zoom_scale
        except:
            logger.warning('Failed to Center Images')
            print_exception()

    def win_x(self, image_x):
        return self.zoom_scale * (image_x + self.ldx + self.dx)

    def win_y(self, image_y):
        return self.zoom_scale * (image_y + self.ldy + self.dy)

    def image_x(self, win_x):
        img_x = (win_x / self.zoom_scale) - self.ldx
        return img_x

    def image_y(self, win_y):
        img_y = (win_y / self.zoom_scale) - self.ldy
        return img_y

    def dump(self):
        print_debug(30, "wheel = " + str(self.wheel_index))
        print_debug(30, "zoom = " + str(self.zoom_scale))
        print_debug(30, "ldx  = " + str(self.ldx))
        print_debug(30, "ldy  = " + str(self.ldy))
        print_debug(30, "mdx  = " + str(self.mdx))
        print_debug(30, "mdy  = " + str(self.mdy))
        print_debug(30, " dx  = " + str(self.dx))
        print_debug(30, " dy  = " + str(self.dy))

    def setFloatBased(self, float_based):
        self.floatBased = float_based
        self.update_zpa_self()

    def setAntialiased(self, antialiased):
        self.antialiased = antialiased
        self.update_zpa_self()

    # # minimum #windowsize #qsize
    # def minimumSizeHint(self):
    #     pass
    #     # return QSize(50, 50)
    #     # return QSize(250, 250) #0719-

    # def sizeHint(self):
    #     pass
    #     # return QSize(180, 180) #0719-
    #     # return

    def mouse_down_callback(self, role, screen_coords, image_coords, button):
        # global match_pt_mode
        # if match_pt_mode.get_value():
        if cfg.main_window.match_point_mode == True:
            logger.info("Adding a match point for role \"" + str(role) + "\" at " + str(
                screen_coords) + " == " + str(image_coords))
            scale_key = cfg.project_data['data']['current_scale']
            layer_num = cfg.project_data['data']['current_layer']
            stack = cfg.project_data['data']['scales'][scale_key]['alignment_stack']
            layer = stack[layer_num]

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
        self.update_zpa_self()
        ex = event.x()
        ey = event.y()

        print('self.role            : %s' % self.role)
        print('(ex, ey)             : %s' % str((ex, ey)))
        print('self.image_x(ex)     : %s' % str(self.image_x(ex)))
        print('self.image_y(ey)     : %s' % str(self.image_y(ey)))
        print('int(event.button())  : %s' % str(int(event.button())))

        event_handled = self.mouse_down_callback(
            self.role,
            (ex, ey),
            (self.image_x(ex), self.image_y(ey)), int(event.button()))


    def mouseMoveEvent(self, event):
        self.update_zpa_self()


    def mouseReleaseEvent(self, event):
        self.update_zpa_self()

    def mouseDoubleClickEvent(self, event):
        print_debug(50, "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()))
        self.update_zpa_self()



    def zoom_to_wheel_at (self, position):
        logger.info('zoom_to_wheel_at:')
        old_scale = self.zoom_scale
        new_scale = self.zoom_scale = pow(self.scroll_factor, self.wheel_index)
        if cfg.USES_QT5:
            logger.info('Using Qt5...')
            # self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale)
            # self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale)
            self.ldx = self.ldx + (position.x() /new_scale) - (position.x()/old_scale)
            self.ldy = self.ldy + (position.y()/new_scale) - (position.y()/old_scale)
            logger.info('self.ldx: %s' % str(self.ldx))
            logger.info('self.ldy: %s' % str(self.ldy))
        else:
            logger.info('Using Qt6...')
            self.ldx = self.ldx + (position.x() / new_scale) - (position.x() / old_scale)
            self.ldy = self.ldy + (position.y() / new_scale) - (position.y() / old_scale)
            logger.info('self.ldx: %s' % str(self.ldx))
            logger.info('self.ldy: %s' % str(self.ldy))


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
            if i in range(n_imgs):
                for role, local_image in stack[i]['images'].items():
                    if local_image['filename'] != None:
                        if len(local_image['filename']) > 0:
                            preload_imgs.add(local_image['filename'])
        cfg.image_library.make_available(preload_imgs)
        if is_dataset_scaled():
            cfg.main_window.read_project_data_update_gui()
        cfg.image_library.update() #orig #0701
        self.update_zpa_self() #orig #0701
        self.update_siblings() # <- change all layers
        # hack to fix bug when proj closed on layer 0 (ref not loaded)
        if self.need_to_center == 1:
            cfg.main_window.center_all_images()
            self.need_to_center = 0
        cfg.main_window.set_idle()

    def wheelEvent(self, event):
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
        '''          type(kmods): <enum 'KeyboardModifier'>
        scroll w/ shift key     :  src.ShiftModifier
        scroll w/out shift key  :  src.NoModifier      '''

        ''''''
        if kmods == Qt.NoModifier:
            # Unshifted Scroll Wheel moves through layers

            # if cfg.USES_QT5 == True:
            #     layer_delta = int(event.delta()/120)    #pyside2
            # else:
            #     layer_delta = event.angleDelta().y()  # 0615 #0719

            layer_delta = event.angleDelta().y()

            # layer_delta = int(event.angleDelta().y() / 120)  # pyside6
            # layer_delta = event.angleDelta().y() # 0615
            # scrolling without shift key pressed...
            # event.angleDelta().y() =  4
            # layer_delta =  0
            # Changing to layer 88
            # scrolling without shift key pressed...
            # event.angleDelta().y() =  2
            # layer_delta =  0
            # Changing to layer 88
            # scrolling without shift key pressed...
            # event.angleDelta().y() =  -2

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

            # logger.info('event.angleDelta().y() = ', event.angleDelta().y())

        elif kmods == Qt.ShiftModifier:
            # Shifted Scroll Wheel zooms
            # if cfg.USES_QT5 == True:
            #     self.wheel_index += event.delta()/120    #pyside2
            # else:
            #     self.wheel_index += event.angleDelta().y()  # 0615

            # self.wheel_index += event.angleDelta().y() / 120  # pyside6
            # self.wheel_index += event.angleDelta().y()  #0615 #0719- orig
            # self.zoom_to_wheel_at(event.x(), event.y())
            # AttributeError: 'PySide6.QtGui.QWheelEvent' object has no attribute 'x'
            '''
            self.wheel_index += event.angleDelta().y()
            self.zoom_to_wheel_at(event.position())  # return type: PySide6.QtCore.QPointF
            '''
            # logger.info('event.angleDelta().y() = ', event.angleDelta().y())

    def paintEvent(self, event):
        # global crop_mode_role  #tag why repeatedly define these globals on each paint event?
        # global crop_mode_disp_rect

        if not self.already_painting:
            self.already_painting = True

            # logger.info("standalone function attempting paintEvent...")

            painter = QPainter(self)

            role_text = self.role
            img_text = None

            #jy 0710
            try:
                if cfg.project_data != None:

                    s = cfg.project_data['data']['current_scale']
                    l = cfg.project_data['data']['current_layer']

                    role_text = str(self.role) + " [" + str(s) + "]" + " [" + str(l) + "]"

                    if len(cfg.project_data['data']['scales']) > 0:
                        # if 1: #monkey patch
                        if len(cfg.project_data['data']['scales'][s]['alignment_stack']) > 0: #debug #tag # previously uncommented

                            image_dict = cfg.project_data['data']['scales'][s]['alignment_stack'][l]['images']
                            is_skipped = cfg.project_data['data']['scales'][s]['alignment_stack'][l]['skip']

                            if self.role in image_dict.keys():
                                ann_image = image_dict[self.role]
                                pixmap = cfg.image_library.get_image_reference(ann_image['filename'])
                                img_text = ann_image['filename']

                                #scale the painter to draw the image as the background
                                painter.scale(self.zoom_scale, self.zoom_scale)

                                if pixmap != None:
                                    if self.draw_border:
                                        pass
                                        # Draw an optional border around the image
                                        # painter.setPen(QPen(QColor(255, 255, 255, 255), 4))
                                        # painter.drawRect(
                                        #     QRectF(self.ldx + self.dx, self.ldy + self.dy, pixmap.width(), pixmap.height()))
                                    # Draw the pixmap itself on top of the border to ensure every pixel is shown
                                    if (not is_skipped) or self.role == 'base':
                                        painter.drawPixmap(QPointF(self.ldx + self.dx, self.ldy + self.dy), pixmap)

                                    # Draw any items that should scale with the image

                                # Rescale the painter to draw items at screen resolution
                                painter.scale(1.0 / self.zoom_scale, 1.0 / self.zoom_scale)

                                # Draw the borders of the viewport for each panel to separate panels
                                # painter.setPen(QPen(self.border_color, 4)) #0523
                                painter.drawRect(painter.viewport()) #0523

                                if self.draw_annotations and (pixmap != None):
                                    if (pixmap.width() > 0) or (pixmap.height() > 0):
                                        painter.setPen(QPen(QColor(128, 255, 128, 255), 5))
                                        painter.drawText(painter.viewport().width() - 100, 40,
                                                         "%dx%d" % (pixmap.width(), pixmap.height()))

                                if self.draw_annotations and 'metadata' in ann_image:
                                    colors = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0], [255, 0, 255],
                                              [0, 255, 255]]
                                    if 'colors' in ann_image['metadata']:
                                        colors = ann_image['metadata']['colors']
                                        print_debug(95, "Colors in metadata = " + str(colors))
                                    if 'annotations' in ann_image['metadata']:
                                        # Draw the application-specific annotations from the metadata
                                        color_index = 0
                                        ann_list = ann_image['metadata']['annotations']
                                        for ann in ann_list:
                                            print_debug(50, "Drawing " + ann)
                                            cmd = ann[:ann.find('(')].strip().lower()
                                            pars = [float(n.strip()) for n in ann[ann.find('(') + 1: -1].split(',')]
                                            print_debug(50, "Command: " + cmd + " with pars: " + str(pars))
                                            if len(pars) >= 4:
                                                color_index = int(pars[3])
                                            else:
                                                color_index = 0

                                            color_to_use = colors[color_index % len(colors)]
                                            print_debug(50, " Color to use: " + str(color_to_use))
                                            painter.setPen(QPen(QColor(*color_to_use), 5))
                                            x = 0
                                            y = 0
                                            r = 0
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

                                if is_skipped:  # skip #redx
                                    self.center_image() #0503 I think this helps
                                    # Draw the red "X" on all images regardless of whether they have the "skipped" annotation
                                    # self.setWindowOpacity(.5)
                                    self.setWindowOpacity(.8)
                                    color_to_use = [255, 50, 50]
                                    painter.setPen(QPen(QColor(*color_to_use), 5))
                                    painter.drawLine(0, 0, painter.viewport().width(), painter.viewport().height())
                                    painter.drawLine(0, painter.viewport().height(), painter.viewport().width(), 0)

                                    # painter.fillRect(rect, QBrush(QColor(128, 128, 255, 128)));

                if self.draw_annotations:
                    # Draw the role
                    painter.setPen(QPen(QColor(255, 100, 100, 255), 5))
                    painter.drawText(10, 20, role_text)
                    if img_text != None:
                        # Draw the image name
                        painter.setPen(QPen(QColor(100, 100, 255, 255), 5))
                        if os.path.sep in img_text:
                            # Only split the path if it's splittable
                            painter.drawText(10, 40, os.path.split(img_text)[-1])
                        else:
                            painter.drawText(10, 40, img_text)

                    if len(cfg.project_data['data']['scales']) > 0:
                        scale = cfg.project_data['data']['scales'][s]
                        if len(scale['alignment_stack']) > 0:
                            layer = scale['alignment_stack'][l]
                            if 'align_to_ref_method' in layer:
                                if 'method_results' in layer['align_to_ref_method']:
                                    method_results = layer['align_to_ref_method']['method_results']
                                    if 'snr_report' in method_results:
                                        if method_results['snr_report'] != None:
                                            painter.setPen(QPen(QColor(255, 255, 255, 255), 5))
                                            midw = painter.viewport().width() / 3
                                            painter.drawText(midw, 20, method_results['snr_report'])


                painter.end()
                del painter

                self.already_painting = False
            except:
                print_exception()
                logger.warning('Something Went Wrong During Paint Event')
                pass


def print_debug(level, p1=None, p2=None, p3=None, p4=None, p5=None):
    debug_level = 0
    if level <= debug_level:
        if p1 == None:
            sys.stderr.write("" + '')
        elif p2 == None:
            sys.stderr.write(str(p1) + '')
        elif p3 == None:
            sys.stderr.write(str(p1) + str(p2) + '')
        elif p4 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + '')
        elif p5 == None:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + '')
        else:
            sys.stderr.write(str(p1) + str(p2) + str(p3) + str(p4) + str(p5) + '')

        try:  # find code_context
            frame = inspect.currentframe()
            if frame:
                code_context = inspect.getframeinfo(frame.f_back).code_context[0].strip()
            else:
                code_context = inspect.stack()[1][4][0].strip()

        finally:
            # Deterministic free references to the frame, to be on the safe side
            del frame
        print('Code context : {}'.format(code_context))
        # print('Value of args: {}\n'.format(args))


