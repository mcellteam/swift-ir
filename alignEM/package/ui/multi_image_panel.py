#!/usr/bin/env python3

import inspect
import logging
from qtpy.QtWidgets import QWidget, QHBoxLayout
from qtpy.QtCore import Qt, QRectF
from qtpy.QtGui import QPainter, QPen, QColor
import config as cfg
from .zoom_pan_widget import ZoomPanWidget

__all__ = ['MultiImagePanel']


class MultiImagePanel(QWidget):

    def __init__(self):
        super(MultiImagePanel, self).__init__()

        p = self.palette()
        p.setColor(self.backgroundRole(), QColor('black'))
        self.setPalette(p)
        self.setAutoFillBackground(True)
        self.setStyleSheet("background-color:black;")

        # self.current_margin = 0
        self.hb_layout = QHBoxLayout()
        # self.update_spacing()
        self.setLayout(self.hb_layout)
        self.actual_children = []
        self.setContentsMargins(0, 0, 0, 0)
        self.draw_border = False
        self.draw_annotations = True
        # self.bg_color = QColor(40, 50, 50, 255)
        self.bg_color = QColor(0, 0, 0, 255) #0407 #color #background
        # self.border_color = QColor(0, 0, 0, 255) #0701 removed

        # QWidgets don't get the keyboard focus by default
        # To have scrolling keys associated with this (multi-panel) widget, set a "StrongFocus"
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  #tag #add #0526 uncommenting, because not certain it does anything and have zoom issue
        self.arrow_direction = 1

    #keypress
    def keyPressEvent(self, event):

        # print("Key press event: " + str(event))

        layer_delta = 0
        if event.key() == Qt.Key_Up:
            layer_delta = 1 * self.arrow_direction
        if event.key() == Qt.Key_Down:
            layer_delta = -1 * self.arrow_direction

        if (layer_delta != 0) and (self.actual_children != None):
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in [panels_to_update[0]]:  # Only update the first one which will update the rest
                p.change_layer(layer_delta)
                p.update_zpa_self()
                p.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        if len(self.actual_children) <= 0:
            # Draw background for no panels
            painter.fillRect(0, 0, self.width(), self.height(), self.bg_color)
            painter.setPen(QPen(QColor(200, 200, 200, 255), 5))
            # painter.setPen(QPen(QColor('#000000'), 5)) #jy
            painter.drawEllipse(QRectF(0, 0, self.width(), self.height()))
            painter.drawText((self.width() / 2) - 140, self.height() / 2, " No Image Roles Defined ")
        else:
            # Draw background for panels
            painter.fillRect(0, 0, self.width(), self.height(), self.bg_color)
        painter.end()

    def update_multi_self(self, exclude=()):
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget) and (not (w in exclude))]
            for p in panels_to_update:
                # p.border_color = self.border_color #0701 removed
                p.update_zpa_self()
                p.repaint()

    def add_panel(self, panel):
        if not panel in self.actual_children:
            self.actual_children.append(panel)
            self.hb_layout.addWidget(panel)
            panel.set_parent(self)
            self.repaint()

    def set_roles(self, roles_list):
        logging.info("MainWindow | MultiImagePanel.set_roles:")
        if len(roles_list) > 0:
            # Save these roles
            role_settings = {}
            for w in self.actual_children:
                if type(w) == ZoomPanWidget:
                    role_settings[w.role] = w.get_settings()

            cfg.project_data['data']['panel_roles'] = roles_list
            # Remove all the image panels (to be replaced)
            try:
                self.remove_all_panels()
            except:
                print("EXCEPTION | MultiImagePanel.set_roles was unable to 'self.remove_all_panels()'")
                pass
            # Create the new panels
            for role in roles_list:
                zpw = ZoomPanWidget(role=role, parent=self)  # focus #zoompanwidget
                # Restore the settings from the previous zpw
                if role in role_settings:
                    zpw.set_settings(role_settings[role])
                # zpw.draw_border = self.draw_border #border #0520
                zpw.draw_annotations = self.draw_annotations
                self.add_panel(zpw)

    def remove_all_panels(self):
        logging.info("MainWindow | MultiImagePanel.remove_all_panels:")
        while len(self.actual_children) > 0:
            self.hb_layout.removeWidget(self.actual_children[-1])
            self.actual_children[-1].deleteLater()
            self.actual_children = self.actual_children[0:-1]
        self.repaint()

    def refresh_all_images(self):
        print('MultiImagePanel.refresh_all_images (caller=%s):' % str(inspect.stack()[1].function))
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.update_zpa_self()
                p.repaint()
        self.repaint()

    def center_all_images(self, all_images_in_stack=True):
        # print('MultiImagePanel.center_all_images (caller=%s):' % str(inspect.stack()[1].function))
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
        print("MultiImagePanel.all_images_actual_size:")
        if self.actual_children != None:
            panels_to_update = [w for w in self.actual_children if (type(w) == ZoomPanWidget)]
            for p in panels_to_update:
                p.show_actual_size()
                p.update_zpa_self()
                p.repaint()
        self.repaint()
