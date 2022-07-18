#!/usr/bin/env python3

import inspect
from qtpy.QtGui import QPainter, QPen, QColor
from qtpy.QtWidgets import QWidget, QRubberBand
from qtpy.QtCore import Qt, QPointF, QRectF, QSize
from qtpy.QtWidgets import QSizePolicy

import config as cfg
from ..utils.print_debug import print_debug
from ..em_utils import get_num_imported_images
from ..em_utils import get_cur_layer
from ..em_utils import get_cur_scale_key
from ..em_utils import print_exception

__all__ = ['ZoomPanWidget']

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

        self.mdx = 0  # Mouse Down x (screen x of mouse down at start of drag)
        self.mdy = 0  # Mouse Down y (screen y of mouse down at start of drag)
        self.ldx = 0  # Last dx (fixed while dragging)
        self.ldy = 0  # Last dy (fixed while dragging)
        self.dx = 0  # Offset in x of the image
        self.dy = 0  # Offset in y of the image

        self.draw_border = False
        self.draw_annotations = True

        self.setAutoFillBackground(True)
        self.setContentsMargins(10, 10, 10, 10)
        # self.border_color = QColor(100, 100, 100, 255)

        # self.setBackgroundRole(QPalette.Base)    #0610 removed
        # self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding) #0610
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.rubberBand = QRubberBand(QRubberBand.Rectangle, self) #0610 removed  #0701 activated

        self.need_to_center = 0

        # self.setToolTip('GlanceEM_SWiFT')  # tooltip #settooltip
        # tooltip.setTargetWidget(btn)
        #
        # self.lb = QLabel(self)
        # self.pixmap = QPixmap("{sims.png}")
        # self.height_label = 100
        # self.lb.resize(self.width(), self.height_label)
        # self.lb.setPixmap(self.pixmap.scaled(self.lb.size(), alignEM.IgnoreAspectRatio))
        # self.show()

        # focus

        #0605 following 6 lines were removed
    #     QApplication.instance().focusChanged.connect(self.on_focusChanged)
    #
    # def on_focusChanged(self):
    #     fwidget = QApplication.focusWidget()
    #     if fwidget is not None:
    #         print("focus widget name = ", fwidget.objectName())

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
        # print('Updating zpa self | Caller: ' + inspect.stack()[1].function + ' |  ZoomPanWidget.update_zpa_self...')
        # Call the super "update" function for this panel's QWidget (this "self")
        if self.parent != None:
            # self.draw_border = self.parent.draw_border #border #0520
            self.draw_annotations = self.parent.draw_annotations
        super(ZoomPanWidget, self).update()

        #04-04 #maybe better at the end of change_layer?
        # TODO FIX
        # if get_cur_snr() is None:
        #     self.setToolTip('%s\n%s\n%s' % ( get_cur_scale_key(), self.role, 'Unaligned' ))
        # else:
        #     self.setToolTip('%s\n%s\n%s' % ( get_cur_scale_key(), self.role, str(get_cur_snr() ) ))

    def show_actual_size(self):
        # print("Showing actual size | ZoomPanWidget.show_actual_size...")
        self.zoom_scale = 1.0
        self.ldx = 0
        self.ldy = 0
        self.wheel_index = 0
        # self.zoom_to_wheel_at ( 0, 0 ) #pyside2 #0613 removed
        self.zoom_to_wheel_at(QPointF(0.0, 0.0))  #pyside6

    # ZoomPanWidget.center_image called once for each role/panel
    def center_image(self, all_images_in_stack=True):
        print("ZoomPanWidget.center_image | called by " + inspect.stack()[1].function)
        # print("  ZoomPanWidget is centering image for " + str(self.role))
        try:
            if cfg.project_data != None:
                # s = get_cur_scale_key()
                s = cfg.project_data['data']['current_scale']
                l = cfg.project_data['data']['current_layer']

                if len(cfg.project_data['data']['scales']) > 0:
                    #print("s = ", s) #0406
                    # if len(cfg.project_data['data']['scales'][s]['alignment_stack']) > 0: #0509
                    if len(cfg.project_data['data']['scales'][s]['alignment_stack']):

                        image_dict = cfg.project_data['data']['scales'][s]['alignment_stack'][l]['images']

                        if self.role in image_dict.keys():
                            # print("current role: ", self.role)
                            ann_image = image_dict[self.role] # <class 'dict'>
                            # class is ZoomPanWidget
                            pixmap = cfg.image_library.get_image_reference(ann_image['filename']) #  <class 'PySide6.QtGui.QPixmap'>

                            if pixmap is None: print("center_image | WARNING | 'pixmap' is set to None")

                            if (pixmap != None) or all_images_in_stack:
                                img_w = 0
                                img_h = 0
                                if pixmap != None:
                                    img_w = pixmap.width()
                                    img_h = pixmap.height()
                                win_w = self.width()
                                win_h = self.height()
                                # print("win_w = %d, win_h = %d" % (win_w, win_h))

                                if all_images_in_stack:
                                    # Search through all images in this stack to find bounds
                                    stack = cfg.project_data['data']['scales'][s]['alignment_stack']
                                    for layer in stack:
                                        if 'images' in layer.keys():
                                            if self.role in layer['images'].keys():
                                                other_pixmap = cfg.image_library.get_image_reference_if_loaded(layer['images'][self.role]['filename'])
                                                if other_pixmap != None:
                                                    other_w = other_pixmap.width()
                                                    other_h = other_pixmap.height()
                                                    img_w = max(img_w, other_w)
                                                    img_h = max(img_h, other_h)

                                if (img_w <= 0) or (img_h <= 0) or (win_w <= 0) or (win_h <= 0):  # Zero or negative dimensions might lock up?
                                    self.need_to_center = 1
                                    print("center_image | WARNING | Image or Window dimension is zero. Cannot center image for role \"" + str(self.role) + "\"")

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
                                    extra_y = 1.7 * extra_y
                                    self.ldx = (extra_x / 2) / self.zoom_scale
                                    self.ldy = (extra_y / 2) / self.zoom_scale
        except:
            print('ZoomPanWidget.center | EXCEPTION | Failed to Center')
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

    # minimum #windowsize #qsize
    def minimumSizeHint(self):
        # return QSize(50, 50)
        return QSize(250, 250)

    def sizeHint(self):
        return QSize(180, 180)

    def mousePressEvent(self, event):
        self.update_zpa_self()


    def mouseMoveEvent(self, event):
        self.update_zpa_self()


    def mouseReleaseEvent(self, event):
        self.update_zpa_self()

    def mouseDoubleClickEvent(self, event):
        print_debug(50, "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()))
        self.update_zpa_self()


    # def zoom_to_wheel_at ( self, mouse_win_x, mouse_win_y ): #pyside2
    def zoom_to_wheel_at(self, position):  # pyside6, position has type PySide6.QtCore.QPoint
        old_scale = self.zoom_scale
        new_scale = self.zoom_scale = pow(self.scroll_factor, self.wheel_index)

        # self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale) #pyside2
        # self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale) #pyside2
        self.ldx = self.ldx + (position.x() / new_scale) - (position.x() / old_scale)
        self.ldy = self.ldy + (position.y() / new_scale) - (position.y() / old_scale)

    def change_layer(self, layer_delta):
        """This function loads the next or previous layer"""
        cfg.main_window.set_status('Loading...')
        cfg.main_window.read_gui_update_project_data()
        n_imgs = get_num_imported_images()
        scale = get_cur_scale_key()
        leaving = get_cur_layer()
        requested = leaving + layer_delta
        rng = cfg.PRELOAD_RANGE
        if requested in range(n_imgs): pass
        elif requested < 0: print('Cant layer down any further!'); cfg.main_window.set_idle(); return
        elif requested > n_imgs - 1: print('Cant layer up any further!'); cfg.main_window.set_idle(); return
        print("Changing to layer %s" % requested)
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
        scroll w/ shift key     :  alignEM.ShiftModifier
        scroll w/out shift key  :  alignEM.NoModifier      '''

        if kmods == Qt.NoModifier:
            # Unshifted Scroll Wheel moves through layers

            # layer_delta = int(event.delta()/120)    #pyside2
            # layer_delta = int(event.angleDelta().y() / 120)  # pyside6
            layer_delta = event.angleDelta().y() # 0615
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

            # print('event.angleDelta().y() = ', event.angleDelta().y())

        elif kmods == Qt.ShiftModifier:
            # Shifted Scroll Wheel zooms
            # self.wheel_index += event.delta()/120    #pyside2
            # self.wheel_index += event.angleDelta().y() / 120  # pyside6
            self.wheel_index += event.angleDelta().y()  #0615
            # self.zoom_to_wheel_at(event.x(), event.y())
            # AttributeError: 'PySide6.QtGui.QWheelEvent' object has no attribute 'x'
            self.zoom_to_wheel_at(event.position())  # return type: PySide6.QtCore.QPointF

            # print('event.angleDelta().y() = ', event.angleDelta().y())

    def paintEvent(self, event):
        # global crop_mode_role  #tag why repeatedly define these globals on each paint event?
        # global crop_mode_disp_rect

        if not self.already_painting:
            self.already_painting = True

            # print("standalone function attempting paintEvent...")

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
                                    self.setWindowOpacity(.5)
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
                print('\nEXCEPTION | ZoomPanWidget Something Went Wrong\n')
                pass
