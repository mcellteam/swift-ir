#!/usr/bin/env python3

import inspect
import logging
from qtpy.QtWidgets import QWidget, QHBoxLayout
from qtpy.QtGui import QPainter, QPen, QColor
import src.config as cfg
from utils.zoom_pan_widget import ZoomPanWidget


__all__ = ['MultiImagePanel']

logger = logging.getLogger(__name__)

class MultiImagePanel(QWidget):
    '''MultiImagePanel is a container around the image panels (roles).
    This class is responsible for initializing ZoomPanWidget.'''

    def __init__(self):
        super(MultiImagePanel, self).__init__()
        self.actual_children = []
        self.zpw = []  # <- List of the individual panels
        self.roles = ['ref', 'base', 'aligned']

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor('black'))
        self.setPalette(p)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color: #000000;")
        self.hb_layout = QHBoxLayout()
        self.setLayout(self.hb_layout)
        self.hb_layout.setContentsMargins(0, 0, 0, 0)
        self.hb_layout.setSpacing(0)
        self.draw_border = False
        self.draw_annotations = True
        # self.bg_color = QColor(40, 50, 50, 255)
        self.bg_color = QColor(0, 0, 0, 255) #0407 # background color
        # self.border_color = QColor(0, 0, 0, 255)
        self.set_roles(self.roles) #0809+



    #keypress
    def keyPressEvent(self, event):
        logger.info("Key press event: " + str(event.key()))
        # layer_delta = 0
        # '''Settings shortcut keys here and also as QShortcuts might be redundant. Will need to test.'''
        # if event.key() == Qt.Key_Right:
        #     if are_images_imported():
        #         layer_delta = 1
        # if event.key() == Qt.Key_Left:
        #     if are_images_imported():
        #         layer_delta = -1
        # if event.key() == Qt.Key_Down:
        #     if do_scales_exist():
        #         if cfg.main_window.scale_down_button.isEnabled():
        #             cfg.main_window.scale_down_button_callback()
        #
        # if event.key() == Qt.Key_Up:
        #     if do_scales_exist():
        #         if cfg.main_window.scale_up_button.isEnabled():
        #             cfg.main_window.scale_up_button_callback()
        #
        # if (layer_delta != 0) and (self.actual_children != None):
        #     panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
        #     for p in [panels_to_update[0]]:  # Only update the first one which will update the rest
        #         p.change_layer(layer_delta) # Actually Change the Layer
        #         p.update_zpa_self() #0827-
        #         p.repaint()

    def get_children(self):
        return [w for w in self.actual_children if (type(w) == ZoomPanWidget)]


    def paintEvent(self, event):
        painter = QPainter(self)
        if len(self.actual_children) <= 0:
            # Background for No Panels
            painter.fillRect(0, 0, self.width(), self.height(), self.bg_color)
            painter.setPen(QPen(QColor(200, 200, 200, 255), 5))
            painter.setPen(QPen(QColor('#000000'), 5))
            # painter.drawEllipse(QRectF(0, 0, self.width(), self.height()))
            # painter.drawText((self.width() / 2) - 140, self.height() / 2, " No Image Roles Defined ")
        else:
            # Background for Panels
            painter.fillRect(0, 0, self.width(), self.height(), self.bg_color)
        # painter = QPainter(self)
        # painter.fillRect(0, 40, self.width(), self.height(), self.bg_color)
        painter.end()

    def update_multi_self(self, exclude=()):
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget) and (not (w in exclude))]
            for p in panels_to_update:
                # p.border_color = self.border_color #0701 removed
                p.update_zpa_self()
                p.repaint()

    def refresh_all_images(self):
        logger.debug('Refreshing all images, called by %s' % str(inspect.stack()[1].function))
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.update_zpa_self()
                p.repaint()
        self.repaint()

    def add_panel(self, panel):
        if not panel in self.actual_children:
            self.actual_children.append(panel)
            self.hb_layout.addWidget(panel)
            panel.set_parent(self)
            self.repaint()

    def set_roles(self, roles_list):
        logger.debug("Setting Roles")
        if len(roles_list) > 0:
            # Save these roles
            role_settings = {}
            for w in self.actual_children:
                if type(w) == ZoomPanWidget:
                    role_settings[w.role] = w.get_settings()

            cfg.data['data']['panel_roles'] = roles_list
            # Remove all the image panels (to be replaced)
            # self.remove_all_panels()
            for i, role in enumerate(roles_list):
                self.zpw.append(ZoomPanWidget(role=role, parent=self))  # focus #zoompanwidget
                # Restore the settings from the previous zpw
                if role in role_settings:
                    self.zpw[i].set_settings(role_settings[role])
                # zpw.draw_border = self.draw_border #border #0520
                self.zpw[i].draw_annotations = self.draw_annotations
                self.add_panel(self.zpw[i])
                cfg.panel_list.append(self.zpw[i])



    def remove_all_panels(self):
        logger.info("MultiImagePanel.remove_all_panels:")
        while len(self.actual_children) > 0:
            self.hb_layout.removeWidget(self.actual_children[-1])
            self.actual_children[-1].deleteLater()
            self.actual_children = self.actual_children[0:-1]
        self.repaint()

    def center_all_images(self, all_images_in_stack=True):
        if self.actual_children != None:
            #NOTE THIS CALL CAN BE USED TO OBTAIN HANDLES TO THE THREE ZoomPanWidget OBJECTS
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.center_image(all_images_in_stack=all_images_in_stack)
                p.update_zpa_self()
                p.repaint()
        self.repaint()
        # self.refresh_all_images() #jy #0701 removed

    def all_images_actual_size(self):
        logger.info("MultiImagePanel.all_images_actual_size:")
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.show_actual_size()
                p.update_zpa_self()
                p.repaint()
        self.repaint()

    def set_style_default(self):
        self.setStyleSheet("background-color: #000000;")

    def set_style_light(self):
        self.setStyleSheet("background-color: #FBFAF0;")

