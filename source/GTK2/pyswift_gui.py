#!/usr/bin/env python

global gtk_mode
gtk_mode = False

if __name__ == '__main__':
  import sys
  if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
      if arg == 'gtk':
        gtk_mode = True
  else:
    gtk_mode = True


#__import__('code').interact(local = locals())

#import numpy as np
#import cv2

global default_plot_code
default_plot_code = """print ( "Default Plotting" )

print ( 'Data is in "d"' )
print ( 'd.keys() = ' + str(d.keys()) )
print ( 'd["data"].keys() = ' + str(d['data'].keys()) )
print ( 'd["data"]["scales"].keys() = ' + str(d['data']['scales'].keys()) )
for k in d['data']['scales'].keys():
  stack = d['data']['scales'][k]['alignment_stack']
  print ( '  d["data"]["scales"][' + k + '].keys() = ' + str(d['data']['scales'][k].keys()) + ' of ' + str(len(stack)) )
  #for s in stack:
  #  print ( "    \"" + s['images']['aligned']['filename'] + "\"" )

import numpy as np
import scipy.stats as sps
import matplotlib.pyplot as plt

# Do Linear Regression of X,Y data
def lin_fit(x,y):
  (m,b,r,p,stderr) = sps.linregress(x,y)
  print('linear regression:')
  return(m,b,r,p,stderr)

sn = str(d['data']['current_scale'])
s = d['data']['scales'][sn]['alignment_stack']
afm = np.array([ i['align_to_ref_method']['method_results']['affine_matrix'] for i in s if 'affine_matrix' in i['align_to_ref_method']['method_results'] ])
cafm = np.array([ i['align_to_ref_method']['method_results']['cumulative_afm'] for i in s if 'cumulative_afm' in i['align_to_ref_method']['method_results'] ])

cx = cafm[:,:,2][:,0]
cy = cafm[:,:,2][:,1]

(mx,bx,r,p,stderr) = lin_fit(np.arange(len(cx)),cx)
(my,by,r,p,stderr) = lin_fit(np.arange(len(cy)),cy)
xl = mx*np.arange(len(cx))+bx
yl = my*np.arange(len(cy))+by

print("(mx,bx): ",mx,bx)
print("(my,by): ",my,by)

p = plt.scatter(np.arange(len(cx)),cx)
p = plt.scatter(np.arange(len(cy)),cy)
p = plt.scatter(np.arange(len(cx)),xl)
p = plt.scatter(np.arange(len(cy)),yl)
plt.show()
"""

global current_plot_code
current_plot_code = ""

import pickle
import base64

import time
import os
import sys
import json
import math
import random
import shutil


if gtk_mode:

  import pygtk
  pygtk.require('2.0')
  import gobject
  import gtk

if not gtk_mode:

  # Make a fake GTK module for constants
  class gtk:
    STATE_NORMAL = None
    def __init__(self):
      self.STATE_NORMAL = None

    # Make a fake GTK.GDK module for constants
    class gdk:
      SCROLL_UP = None
      SCROLL_DOWN = None
      EXPOSURE_MASK = None
      ENTER_NOTIFY_MASK = None
      LEAVE_NOTIFY_MASK = None
      KEY_PRESS_MASK = None
      BUTTON_PRESS_MASK = None
      BUTTON_RELEASE_MASK = None
      POINTER_MOTION_MASK = None
      POINTER_MOTION_HINT_MASK = None
      CONTROL_MASK = None
      CROSSHAIR = None
      TARGET = None
      X_CURSOR = None
      PLUS = None
      DOTBOX = None
      CROSS = None
      HAND1 = None
      HAND2 = None
      ARROW = None
      BASED_ARROW_DOWN = None
      BASED_ARROW_UP = None
      XXXXXX = None
      def __init__(self):
        self.SCROLL_UP = None
        self.SCROLL_DOWN = None
        self.EXPOSURE_MASK = None
        self.ENTER_NOTIFY_MASK = None
        self.LEAVE_NOTIFY_MASK = None
        self.KEY_PRESS_MASK = None
        self.BUTTON_PRESS_MASK = None
        self.BUTTON_RELEASE_MASK = None
        self.POINTER_MOTION_MASK = None
        self.POINTER_MOTION_HINT_MASK = None
        self.CONTROL_MASK = None
        self.CROSSHAIR = None
        self.TARGET = None
        self.X_CURSOR = None
        self.PLUS = None
        self.DOTBOX = None
        self.CROSS = None
        self.HAND1 = None
        self.HAND2 = None
        self.ARROW = None
        self.BASED_ARROW_DOWN = None
        self.BASED_ARROW_UP = None
        self.XXXXXX = None


''' Available GTK Cursors - some with descriptions

  DOTBOX - box with midpoint ticks indicating center
  TARGET - box with midpoint ticks indicating center (same as DOTBOX?)
  CROSS - thin +
  CROSSHAIR - thin +
  CROSS_REVERSE - thin +
  DIAMOND_CROSS - thin +
  PLUS - thick +
  X_CURSOR - thick X
  IRON_CROSS - might show center point somewhat
  DOT - white circle with black fill
  HAND2 - pointing
  HAND1 - pointing
  CIRCLE - Normal arrow with a small circle near shaft
  CENTER_PTR - Arrow pointing up
  STAR - 5 point star

  ARROW
  BASED_ARROW_DOWN
  BASED_ARROW_UP
  BOAT
  BOGOSITY
  BOTTOM_LEFT_CORNER
  BOTTOM_RIGHT_CORNER
  BOTTOM_SIDE
  BOTTOM_TEE
  BOX_SPIRAL
  CLOCK
  COFFEE_MUG
  DOUBLE_ARROW
  DRAFT_LARGE
  DRAFT_SMALL
  DRAPED_BOX
  EXCHANGE
  FLEUR
  GOBBLER
  GUMBY
  HEART
  ICON
  LEFT_PTR
  LEFT_SIDE
  LEFT_TEE
  LEFTBUTTON
  LL_ANGLE
  LR_ANGLE
  MAN
  MIDDLEBUTTON
  MOUSE
  PENCIL
  PIRATE
  QUESTION_ARROW
  RIGHT_PTR
  RIGHT_SIDE
  RIGHT_TEE
  RIGHTBUTTON
  RTL_LOGO
  SAILBOAT
  SB_DOWN_ARROW
  SB_H_DOUBLE_ARROW
  SB_LEFT_ARROW
  SB_RIGHT_ARROW
  SB_UP_ARROW
  SB_V_DOUBLE_ARROW
  SHUTTLE
  SIZING
  SPIDER
  SPRAYCAN
  TCROSS
  TOP_LEFT_ARROW
  TOP_LEFT_CORNER
  TOP_RIGHT_CORNER
  TOP_SIDE
  TOP_TEE
  TREK
  UL_ANGLE
  UMBRELLA
  UR_ANGLE
  WATCH
  XTERM
  CURSOR_IS_PIXMAP
'''

global cursor_options
cursor_options = [
    ["Cursor_CROSSHAIR", gtk.gdk.CROSSHAIR],
    ["Cursor_TARGET",    gtk.gdk.TARGET],
    ["Cursor_X_CURSOR",  gtk.gdk.X_CURSOR],
    ["Cursor_PLUS",      gtk.gdk.PLUS],
    ["Cursor_DOTBOX",    gtk.gdk.DOTBOX],
    ["Cursor_CROSS",     gtk.gdk.CROSS],
    ["Cursor_HAND1",     gtk.gdk.HAND1],
    ["Cursor_HAND2",     gtk.gdk.HAND2],
    ["Cursor_ARROW",     gtk.gdk.ARROW],
    ["Cursor_BASED_ARROW_DOWN", gtk.gdk.BASED_ARROW_DOWN],
    ["Cursor_BASED_ARROW_UP", gtk.gdk.BASED_ARROW_UP]
    #["Cursor_BOAT", gtk.gdk.BOAT],
    #["Cursor_BOGOSITY", gtk.gdk.BOGOSITY],
    #["Cursor_BOTTOM_LEFT_CORNER", gtk.gdk.BOTTOM_LEFT_CORNER],
    #["Cursor_BOTTOM_RIGHT_CORNER", gtk.gdk.BOTTOM_RIGHT_CORNER],
    #["Cursor_BOTTOM_SIDE", gtk.gdk.BOTTOM_SIDE],
    #["Cursor_BOTTOM_TEE", gtk.gdk.BOTTOM_TEE],
    #["Cursor_BOX_SPIRAL", gtk.gdk.BOX_SPIRAL],
    #["Cursor_CLOCK", gtk.gdk.CLOCK],
    #["Cursor_COFFEE_MUG", gtk.gdk.COFFEE_MUG],
    #["Cursor_DOUBLE_ARROW", gtk.gdk.DOUBLE_ARROW],
    #["Cursor_DRAFT_LARGE", gtk.gdk.DRAFT_LARGE],
    #["Cursor_DRAFT_SMALL", gtk.gdk.DRAFT_SMALL],
    #["Cursor_DRAPED_BOX", gtk.gdk.DRAPED_BOX],
    #["Cursor_EXCHANGE", gtk.gdk.EXCHANGE],
    #["Cursor_FLEUR", gtk.gdk.FLEUR],
    #["Cursor_GOBBLER", gtk.gdk.GOBBLER],
    #["Cursor_GUMBY", gtk.gdk.GUMBY],
    #["Cursor_HEART", gtk.gdk.HEART],
    #["Cursor_ICON", gtk.gdk.ICON],
    #["Cursor_LEFT_PTR", gtk.gdk.LEFT_PTR],
    #["Cursor_LEFT_SIDE", gtk.gdk.LEFT_SIDE],
    #["Cursor_LEFT_TEE", gtk.gdk.LEFT_TEE],
    #["Cursor_LEFTBUTTON", gtk.gdk.LEFTBUTTON],
    #["Cursor_LL_ANGLE", gtk.gdk.LL_ANGLE],
    #["Cursor_LR_ANGLE", gtk.gdk.LR_ANGLE],
    #["Cursor_MAN", gtk.gdk.MAN],
    #["Cursor_MIDDLEBUTTON", gtk.gdk.MIDDLEBUTTON],
    #["Cursor_MOUSE", gtk.gdk.MOUSE],
    #["Cursor_PENCIL", gtk.gdk.PENCIL],
    #["Cursor_PIRATE", gtk.gdk.PIRATE],
    #["Cursor_QUESTION_ARROW", gtk.gdk.QUESTION_ARROW],
    #["Cursor_RIGHT_PTR", gtk.gdk.RIGHT_PTR],
    #["Cursor_RIGHT_SIDE", gtk.gdk.RIGHT_SIDE],
    #["Cursor_RIGHT_TEE", gtk.gdk.RIGHT_TEE],
    #["Cursor_RIGHTBUTTON", gtk.gdk.RIGHTBUTTON],
    #["Cursor_RTL_LOGO", gtk.gdk.RTL_LOGO],
    #["Cursor_SAILBOAT", gtk.gdk.SAILBOAT],
    #["Cursor_SB_DOWN_ARROW", gtk.gdk.SB_DOWN_ARROW],
    #["Cursor_SB_H_DOUBLE_ARROW", gtk.gdk.SB_H_DOUBLE_ARROW],
    #["Cursor_SB_LEFT_ARROW", gtk.gdk.SB_LEFT_ARROW],
    #["Cursor_SB_RIGHT_ARROW", gtk.gdk.SB_RIGHT_ARROW],
    #["Cursor_SB_UP_ARROW", gtk.gdk.SB_UP_ARROW],
    #["Cursor_SB_V_DOUBLE_ARROW", gtk.gdk.SB_V_DOUBLE_ARROW],
    #["Cursor_SHUTTLE", gtk.gdk.SHUTTLE],
    #["Cursor_SIZING", gtk.gdk.SIZING],
    #["Cursor_SPIDER", gtk.gdk.SPIDER],
    #["Cursor_SPRAYCAN", gtk.gdk.SPRAYCAN],
    #["Cursor_TCROSS", gtk.gdk.TCROSS],
    #["Cursor_TOP_LEFT_ARROW", gtk.gdk.TOP_LEFT_ARROW],
    #["Cursor_TOP_LEFT_CORNER", gtk.gdk.TOP_LEFT_CORNER],
    #["Cursor_TOP_RIGHT_CORNER", gtk.gdk.TOP_RIGHT_CORNER],
    #["Cursor_TOP_SIDE", gtk.gdk.TOP_SIDE],
    #["Cursor_TOP_TEE", gtk.gdk.TOP_TEE],
    #["Cursor_TREK", gtk.gdk.TREK],
    #["Cursor_UL_ANGLE", gtk.gdk.UL_ANGLE],
    #["Cursor_UMBRELLA", gtk.gdk.UMBRELLA],
    #["Cursor_UR_ANGLE", gtk.gdk.UR_ANGLE],
    #["Cursor_WATCH", gtk.gdk.WATCH],   # Animated "waiting" cursor!!
    #["Cursor_XTERM", gtk.gdk.XTERM]
    # ["Cursor_CURSOR_IS_PIXMAP", gtk.gdk.CURSOR_IS_PIXMAP]  # This will crash!!
  ]

#######################################################################################################

if not gtk_mode:

  ##  QT Version Code

  import sys
  import argparse
  import cv2

  from PySide2 import QtWidgets  # This was done in the standarddialogs.py example
  from PySide2.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QAction, QSizePolicy, QGridLayout, QLineEdit
  from PySide2.QtGui import QPixmap, QColor, QPainter, QPalette, QPen
  from PySide2.QtCore import Slot, qApp, QRect, QRectF, QSize, Qt, QPoint, QPointF

  import py_swift_tiff

  class app_window:

    class zoom_pan_area(QWidget):
        def __init__(self, parent=None, win_width=1280, win_height=1024, fname=None):

            super(app_window.zoom_pan_area, self).__init__(parent)

            self.fname = fname
            self.pixmap = None

            if self.fname != None:
              if len(self.fname) > 0:
                self.pixmap = QPixmap(fname)

            self.floatBased = False
            self.antialiased = False
            self.wheel_index = 0
            self.scroll_factor = 1.25
            self.zoom_scale = 1.0
            self.last_button = Qt.MouseButton.NoButton

            self.mdx = 0  # Mouse Down x (screen x of mouse down at start of drag)
            self.mdy = 0  # Mouse Down y (screen y of mouse down at start of drag)
            self.ldx = 0  # Last dx (fixed while dragging)
            self.ldy = 0  # Last dy (fixed while dragging)
            self.dx = 0   # Offset in x of the image
            self.dy = 0   # Offset in y of the image

            self.setBackgroundRole(QPalette.Base)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        def image_x ( self, win_x ):
            img_x = (win_x/self.zoom_scale) - self.ldx
            return ( img_x )

        def image_y ( self, win_y ):
            img_y = (win_y/self.zoom_scale) - self.ldy
            return ( img_y )

        def dump(self):
            print ( "wheel = " + str(self.wheel_index) )
            print ( "zoom = " + str(self.zoom_scale) )
            print ( "ldx  = " + str(self.ldx) )
            print ( "ldy  = " + str(self.ldy) )
            print ( "mdx  = " + str(self.mdx) )
            print ( "mdy  = " + str(self.mdy) )
            print ( " dx  = " + str(self.dx) )
            print ( " dy  = " + str(self.dy) )

        def setFloatBased(self, floatBased):
            self.floatBased = floatBased
            self.update()

        def setAntialiased(self, antialiased):
            self.antialiased = antialiased
            self.update()

        def minimumSizeHint(self):
            return QSize(50, 50)

        def sizeHint(self):
            return QSize(180, 180)

        def mousePressEvent(self, event):
            ex = event.x()
            ey = event.y()

            self.last_button = event.button()
            if event.button() == Qt.MouseButton.RightButton:
                # Resest the pan and zoom
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
            self.update()

        def mouseMoveEvent(self, event):
            if self.last_button == Qt.MouseButton.LeftButton:
                self.dx = (event.x() - self.mdx) / self.zoom_scale
                self.dy = (event.y() - self.mdy) / self.zoom_scale
                self.update()

        def mouseReleaseEvent(self, event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.ldx = self.ldx + self.dx
                self.ldy = self.ldy + self.dy
                self.dx = 0
                self.dy = 0
                self.update()

        def mouseDoubleClickEvent(self, event):
            print ( "mouseDoubleClickEvent at " + str(event.x()) + ", " + str(event.y()) )
            self.update()

        def wheelEvent(self, event):
            self.wheel_index += event.delta()/120

            mouse_win_x = event.x()
            mouse_win_y = event.y()

            old_scale = self.zoom_scale
            new_scale = self.zoom_scale = pow (self.scroll_factor, self.wheel_index)

            self.ldx = self.ldx + (mouse_win_x/new_scale) - (mouse_win_x/old_scale)
            self.ldy = self.ldy + (mouse_win_y/new_scale) - (mouse_win_y/old_scale)

            self.update()

        def paintEvent(self, event):
            painter = QPainter(self)

            if True:
                if self.pixmap != None:
                    painter.scale ( self.zoom_scale, self.zoom_scale )
                    painter.drawPixmap ( QPointF(self.ldx+self.dx,self.ldy+self.dy), self.pixmap )
            else:
                painter.setRenderHint(QPainter.Antialiasing, self.antialiased)
                painter.translate(self.width() / 2, self.height() / 2)
                for diameter in range(0, 256, 9):
                    delta = abs((self.wheel_index % 128) - diameter / 2)
                    alpha = 255 - (delta * delta) / 4 - diameter
                    if alpha > 0:
                        painter.setPen(QPen(QColor(0, diameter / 2, 127, alpha), 3))
                        if self.floatBased:
                            painter.drawEllipse(QRectF(-diameter / 2.0,
                                    -diameter / 2.0, diameter, diameter))
                        else:
                            painter.drawEllipse(QRect(-diameter / 2,
                                    -diameter / 2, diameter, diameter))


    # MainWindow contains the Menu Bar and the Status Bar
    class MainWindow(QMainWindow):

        def __init__(self, fname):

            QMainWindow.__init__(self)
            self.setWindowTitle("PySide2 Image Viewer")

            print ( "Begin loading fixed names for fixed panels" )
            self.zpa1 = app_window.zoom_pan_area(fname=fname)
            self.zpa2 = app_window.zoom_pan_area(fname=fname)
            print ( "Done loading fixed names for fixed panels" )

            # Menu Bar
            self.menu = self.menuBar()
            ml = [
                  [ '&File',
                    [
                      [ '&New Project', 'Ctrl+N', self.not_yet ],
                      [ '&Open Project', 'Ctrl+O', self.open_project ],
                      [ '&Save Project', 'Ctrl+S', self.not_yet ],
                      [ 'Save Project &As', 'Ctrl+A', self.not_yet ],
                      [ '-', None, None ],
                      [ 'Set Destination...', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'E&xit', 'Ctrl+Q', self.exit_app ]
                    ]
                  ],
                  [ '&Images',
                    [
                      [ '&Import...', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Center', None, self.not_yet ],
                      [ 'Actual Size', None, self.not_yet ],
                      [ 'Refresh', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Clear Out Images', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Clear All Layers', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Clear Everything', None, self.not_yet ]
                    ]
                  ],
                  [ '&Scaling',
                    [
                      [ '&Define Scales', None, self.not_yet ],
                      [ '&Generate All Scales', None, self.not_yet ],
                      [ '&Import All Scales', None, self.not_yet ],
                      [ '-', None, None ],
                      [ '&Generate Tiled', None, self.not_yet ],
                      [ '&Import Tiled', None, self.not_yet ],
                      [ '&Show Tiled', None, self.not_yet ]
                    ]
                  ],
                  [ '&Scales',
                    [
                      [ '&Scale 1', None, self.not_yet ]
                    ]
                  ],
                  [ '&Points',
                    [
                      [ '&Alignment Point Mode', None, self.not_yet ],
                      [ '&Delete Points', None, self.not_yet ],
                      [ '&Clear All Alignment Points', None, self.not_yet ],
                      [ '-', None, None ],
                      [ '&Point Cursor',
                        [
                          [ 'Crosshair', None, self.not_yet ],
                          [ 'Target', None, self.not_yet ]
                        ]
                      ]
                    ]
                  ],
                  [ '&Set',
                    [
                      [ '&Max Image Size', 'Ctrl+M', self.not_yet ],
                      [ '-', None, None ],
                      [ 'Perform Swims', None, self.not_yet ],
                      [ 'Update CFMs', None, self.not_yet ],
                      [ 'Generate Images', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Use C Version', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Unlimited Zoom', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Default Plot Code', None, self.not_yet ],
                      [ 'Custom Plot Code', None, self.not_yet ],
                    ]
                  ],
                  [ '&Show',
                    [
                      [ 'Window Centers', None, self.not_yet ],
                      [ 'Affines', None, self.not_yet ],
                      [ 'Skipped Images', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Plot', None, self.not_yet ],
                    ]
                  ],
                  [ '&Debug',
                    [
                      [ '&Python Console', 'Ctrl+P', self.py_console ],
                      [ '-', None, None ],
                      [ 'Print Affine', None, self.not_yet ],
                      [ 'Print Structures', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Define Waves', None, self.not_yet ],
                      [ 'Make Waves', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Define Grid', None, self.not_yet ],
                      [ 'Grid Align', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Show Waves', None, self.not_yet ],
                      [ 'Show Grid Align', None, self.not_yet ],
                      [ 'Show Aligned', None, self.not_yet ],
                      [ '-', None, None ],
                      [ '&Set Debug Level',
                        [
                          [ 'Level 0', None, self.debug_0, 'level' ],
                          [ 'Level 10', None, self.debug_10, 'level' ],
                          [ 'Level 20', None, self.debug_20, 'level' ],
                          [ 'Level 30', None, self.debug_30, 'level' ],
                          [ 'Level 40', None, self.debug_40, 'level' ],
                          [ 'Level 50', None, self.debug_50, 'level' ],
                          [ 'Level 60', None, self.debug_60, 'level' ],
                          [ 'Level 70', None, self.debug_70, 'level' ],
                          [ 'Level 80', None, self.debug_80, 'level' ],
                          [ 'Level 90', None, self.debug_90, 'level' ],
                          [ 'Level 100', None, self.debug_100, 'level' ]
                        ]
                      ]
                    ]
                  ],
                  [ '&Help',
                    [
                      [ 'Manual...', None, self.not_yet ],
                      [ 'Key Commands...', None, self.not_yet ],
                      [ 'Mouse Clicks...', None, self.not_yet ],
                      [ '-', None, None ],
                      [ 'Skipped Images', None, self.not_yet ],
                      [ 'License...', None, self.not_yet ],
                      [ 'Version...', None, self.not_yet ]
                    ]
                  ]
                ]
            self.build_menu_from_list ( self.menu, ml )

            # Status Bar
            self.status = self.statusBar()
            self.status.showMessage("File: "+fname)

            # Window dimensions
            geometry = qApp.desktop().availableGeometry(self)
            # self.setFixedSize(geometry.width() * 0.8, geometry.height() * 0.7)
            self.setMinimumWidth(1400)
            self.setMinimumHeight(1024)

            self.central_widget = QWidget()
            central_layout = QGridLayout()
            central_layout.addWidget ( self.zpa1, 0, 0 )
            central_layout.addWidget ( self.zpa2, 0, 1 )

            self.control_panel = QWidget()
            control_panel_layout = QGridLayout()

            gui_fields.proj_label = QLabel ( "Project File" )
            # gui_fields.proj_label.setAlignment ( "" )
            control_panel_layout.addWidget ( gui_fields.proj_label, 0, 0 )

            gui_fields.dest_label = QLabel ( "Destination" )
            control_panel_layout.addWidget ( gui_fields.dest_label, 1, 0 )

            self.row_3 = QLineEdit ( "Jump To" )
            control_panel_layout.addWidget ( self.row_3, 2, 0 )

            self.row_4 = QLineEdit ( "SNR Skip" )
            control_panel_layout.addWidget ( self.row_4, 3, 0 )

            self.row_5 = QLineEdit ( "Internal Swim" )
            control_panel_layout.addWidget ( self.row_5, 4, 0 )

            self.row_6 = QLineEdit ( "Init Affine" )
            control_panel_layout.addWidget ( self.row_6, 5, 0 )

            self.row_7 = QLineEdit ( "Align All" )
            control_panel_layout.addWidget ( self.row_7, 6, 0 )


            self.control_panel.setLayout(control_panel_layout)


            central_layout.addWidget ( self.control_panel, 1, 0, 1, 2 )
            self.central_widget.setLayout(central_layout)

            self.setCentralWidget(self.central_widget)
            #self.setCentralWidget(self.zpa1)
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        def build_menu_from_list (self, parent, menu_list):
            for item in menu_list:
              if type(item[1]) == type([]):
                # This is a submenu
                sub = parent.addMenu(item[0])
                self.build_menu_from_list ( sub, item[1] )
              else:
                # This is a menu item (action) or a separator
                if item[0] == '-':
                  # This is a separator
                  parent.addSeparator()
                else:
                  # This is a menu item (action) with name, accel, callback
                  action = QAction ( item[0], self )
                  if item[1] != None:
                    action.setShortcut ( item[1] )
                  if item[2] != None:
                    action.triggered.connect ( item[2] )
                  parent.addAction ( action )
                  if (len(item) >= 4) and (type(item[3])==type(None)):
                    # This is either a radio button menu item or a checkbox menu item
                    if type(item[3])==type(None):
                      # This is a checkbox item
                      pass
                    else:
                      # This is a radio button item with the 4th value as a group name
                      pass
                  else:
                    # This is a normal menu item
                    pass


        @Slot()
        def not_yet(self, checked):
            print ( "Function is not implemented yet" )

        @Slot()
        def exit_app(self, checked):
            sys.exit()

        @Slot()
        def py_console(self, checked):
            print ( "\n\nEntering python console, use Control-D or Control-Z when done.\n" )
            __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        @Slot()
        def debug_0(self, checked):
            print ( "\nSetting debug_level to 0.\n" )
            global debug_level
            debug_level = 0

        @Slot()
        def debug_10(self, checked):
            print ( "\nSetting debug_level to 10.\n" )
            global debug_level
            debug_level = 10

        @Slot()
        def debug_20(self, checked):
            print ( "\nSetting debug_level to 20.\n" )
            global debug_level
            debug_level = 20

        @Slot()
        def debug_30(self, checked):
            print ( "\nSetting debug_level to 30.\n" )
            global debug_level
            debug_level = 30

        @Slot()
        def debug_40(self, checked):
            print ( "\nSetting debug_level to 40.\n" )
            global debug_level
            debug_level = 40

        @Slot()
        def debug_50(self, checked):
            print ( "\nSetting debug_level to 50.\n" )
            global debug_level
            debug_level = 50

        @Slot()
        def debug_60(self, checked):
            print ( "\nSetting debug_level to 60.\n" )
            global debug_level
            debug_level = 60

        @Slot()
        def debug_70(self, checked):
            print ( "\nSetting debug_level to 70.\n" )
            global debug_level
            debug_level = 70

        @Slot()
        def debug_80(self, checked):
            print ( "\nSetting debug_level to 80.\n" )
            global debug_level
            debug_level = 80

        @Slot()
        def debug_90(self, checked):
            print ( "\nSetting debug_level to 90.\n" )
            global debug_level
            debug_level = 90

        @Slot()
        def debug_100(self, checked):
            print ( "\nSetting debug_level to 100.\n" )
            global debug_level
            debug_level = 100


        @Slot()
        def open_project(self, checked):

            global debug_level

            global project_path
            global project_file_name
            global destination_path
            global zpa_original
            global scales_dict
            global current_scale
            global alignment_layer_list
            global alignment_layer_index
            global panel_list
            global import_tiled

            global point_cursor
            global cursor_options
            global point_mode
            global point_delete_mode

            global code_dialog
            global code_store
            global code_entry
            global current_plot_code

            global generate_as_tiled

            print ( "\nOpening Project.\n" )

            options = QtWidgets.QFileDialog.Options()
            if not True:  # self.native.isChecked():
                options |= QtWidgets.QFileDialog.DontUseNativeDialog
            open_name, filtr = QtWidgets.QFileDialog.getOpenFileName(self,
                    "QFileDialog.getOpenFileName()",
                    #self.openFileNameLabel.text(),
                    "Open a Project",
                    "JSON Files (*.json);;All Files (*)", "", options)
            if open_name:
              print ( "Opening " + open_name )
              if open_name != None:
                open_name = os.path.realpath(open_name)
                if not os.path.isdir(open_name):
                  # It's a real file
                  project_file_name = open_name
                  project_path = os.path.dirname(project_file_name)

                  global gtk_mode
                  if gtk_mode:
                    gui_fields.proj_label.set_text ( "Project File: " + str(project_file_name) )
                  else:
                    gui_fields.proj_label.setText ( "Project File: " + str(project_file_name) )

                  f = open ( project_file_name, 'r' )
                  text = f.read()
                  f.close()

                  proj_dict = json.loads ( text )
                  print_debug ( 70, str(proj_dict) )
                  print_debug ( 5, "Project file version " + str(proj_dict['version']) )

                  load_from_proj_dict ( proj_dict )

                  '''
                  # Test to explore how the JSONEncoder works for indenting JSON output
                  # This works reasonably well, but short arrays and dictionaries are not in-line
                  # Also note that this must be done BEFORE calling load_from_proj_dict
                  # This is because load_from_proj_dict appears to add non-JSON compatible objects
                  '''

                  ''' In later tests this gives an error ... so comment out

                    Saving JSON to "test_json_output.json"
                    Traceback (most recent call last):
                      File "pyswift_gui.py", line 2547, in menu_callback
                        proj_encoded_dict = jdencode.encode ( proj_dict )
                      File "/usr/lib/python2.7/json/encoder.py", line 209, in encode
                        chunks = list(chunks)
                      File "/usr/lib/python2.7/json/encoder.py", line 434, in _iterencode
                        for chunk in _iterencode_dict(o, _current_indent_level):
                      File "/usr/lib/python2.7/json/encoder.py", line 408, in _iterencode_dict
                        for chunk in chunks:
                      File "/usr/lib/python2.7/json/encoder.py", line 408, in _iterencode_dict
                        for chunk in chunks:
                      File "/usr/lib/python2.7/json/encoder.py", line 408, in _iterencode_dict
                        for chunk in chunks:
                      File "/usr/lib/python2.7/json/encoder.py", line 332, in _iterencode_list
                        for chunk in chunks:
                      File "/usr/lib/python2.7/json/encoder.py", line 442, in _iterencode
                        o = _default(o)
                      File "/usr/lib/python2.7/json/encoder.py", line 184, in default
                        raise TypeError(repr(o) + " is not JSON serializable")
                    TypeError: <__main__.alignment_layer instance at 0x7f9fe9a89a28> is not JSON serializable

                  print_debug ( 0, "Saving JSON to \"test_json_output.json\"" )
                  jdencode = json.JSONEncoder ( indent=2, separators=(",", ": ") )
                  if False:
                    proj_encoded_dict = jdencode.iterencode ( proj_dict )
                    f = open ( "test_json_output.json", 'w' )
                    for chunk in proj_encoded_dict:
                      f.write ( chunk )
                    f.close()
                  else:
                    proj_encoded_dict = jdencode.encode ( proj_dict )
                    f = open ( "test_json_output.json", 'w' )
                    f.write ( proj_encoded_dict )
                    f.close()
                  '''



            """
            file_chooser.destroy()
            print_debug ( 90, "Done with dialog" )

            update_newly_loaded_proj()
            """


# import app_window

if gtk_mode:

  class app_window:

    # Provide an interface to a user application that ...
    #
    #  - Allows direct use of all GTK drawing commands
    #  - Allows most code to work with user coordinates
    #  - Provides simple coordinate transform functions
    #  - Transparent zoom and pan
    #  - Application controlled zoom and pan requests
    #  - Application controlled window sizing requests
    #  - Easy menu interface (may be a separate module)
    #  - Easy status bar interface (may be a separate module)
    #
    #  - Define initial scaling and window size:
    #      win.set_x_scale ( 0.0,   0,  1.0, 640 )
    #      win.set_y_scale ( 0.0, 480,  1.0,   0 )
    #      win.set_fixed_aspect ( True )
    #      win.set_scroll_factor ( 1.1 )
    #  - Query current window size:
    #      win.get_x_min ()
    #      win.get_x_max ()
    #      win.get_y_min ()
    #      win.get_y_max ()
    #  - Request refit
    #      win.fitwidth  ( -3.1, 7.6, keep_aspect=False ) # implies left to right
    #      win.fitheight (  200, 0.0, keep_aspect=False ) # implies top to bottom
    #  - Convert user coordinates to window coordinates for drawing
    #      win.wx ( user_x )
    #      win.wy ( user_y )
    #      win.ww ( user_w )
    #      win.wh ( user_h )
    #  - Convert window coordinates to user coordinates for callbacks
    #      win.x ( win_x )
    #      win.y ( win_y )
    #      win.w ( win_w )
    #      win.h ( win_h )

    #
    #  - Drawing callback
    #      pixmap.draw_rectangle ( gc, True, win.x(0.33), win.y(1.2), win.w(0.5), win.h(0.1) )


    #__import__('code').interact(local = locals())


    class zoom_pan_area:

      def __init__( self, window, win_width, win_height, name="" ):
        # These are defined to move from user space to graphics space
        self.window = window
        self.name = name
        self.set_defaults()
        self.drawing_area = gtk.DrawingArea()
        self.drawing_area.set_flags ( gtk.CAN_FOCUS )
        self.drawing_area.set_size_request(win_width,win_height)

        # self.drawing_area.connect ( "expose_event", expose_callback, self )
        self.drawing_area.connect ( "scroll_event", self.mouse_scroll_callback, self )
        self.drawing_area.connect ( "key_press_event", self.key_press_callback, self )
        self.drawing_area.connect ( "button_press_event", self.button_press_callback, self )
        self.drawing_area.connect ( "button_release_event", self.button_release_callback, self )
        self.drawing_area.connect ( "motion_notify_event", self.mouse_motion_callback, self )

        self.drawing_area.set_events ( gtk.gdk.EXPOSURE_MASK
                                     | gtk.gdk.ENTER_NOTIFY_MASK
                                     | gtk.gdk.LEAVE_NOTIFY_MASK
                                     | gtk.gdk.KEY_PRESS_MASK
                                     | gtk.gdk.BUTTON_PRESS_MASK
                                     | gtk.gdk.BUTTON_RELEASE_MASK
                                     | gtk.gdk.POINTER_MOTION_MASK
                                     | gtk.gdk.POINTER_MOTION_HINT_MASK )

        self.accel_group = gtk.AccelGroup()
        self.window.add_accel_group(self.accel_group)

        self.user_data = None

      def set_defaults ( self ):
        self.x_offset = self.reset_x_offset = 0.0
        self.y_offset = self.reset_y_offset = 0.0
        self.x_scale = self.reset_x_scale = 1.0
        self.y_scale = self.reset_y_scale = 1.0
        self.aspect_fixed = True
        self.scroll_count = 0
        self.scroll_factor = 1.25
        self.zoom_scale = 1.0
        self.dragging = False
        self.last_x = 0
        self.last_y = 0
        self.max_zoom_count = 10
        self.min_zoom_count = -15

      def reset_view ( self ):
        #self.set_defaults()
        self.x_offset = self.reset_x_offset
        self.y_offset = self.reset_y_offset
        self.x_scale = self.reset_x_scale
        self.y_scale = self.reset_y_scale
        self.scroll_count = 0
        self.zoom_scale = 1.0
        self.drawing_area.queue_draw()

      def set_x_scale ( self, user_x1, win_x1, user_x2, win_x2 ):
        # Note that this sets the scale regardless of the scrolling zoom
        self.x_scale  = self.reset_x_scale = float(win_x2 - win_x1) / (user_x2 - user_x1)
        self.x_offset = self.reset_x_offset = win_x1 - ( user_x1 * self.x_scale )

      def set_y_scale ( self, user_y1, win_y1, user_y2, win_y2 ):
        # Note that this sets the scale regardless of the scrolling zoom
        self.y_scale  = self.reset_y_scale = float(win_y2 - win_y1) / (user_y2 - user_y1)
        self.y_offset = self.reset_y_offset = win_y1 - ( user_y1 * self.y_scale )

      def set_fixed_aspect ( self, fixed_aspect ):
        pass
      def fitwidth  ( self, user_xmin, user_xmax, keep_aspect=False ):
        pass  # implies left to right
      def fitheight ( self, user_ymin, user_ymax, keep_aspect=False ):
        pass # implies top to bottom

      def set_scroll_factor ( self, scroll_factor ):
        pass

      def set_scale_to_fit ( self, x_min, x_max, y_min, y_max, w, h ):
        if False:
          # This will fill the window completely stretching the image as needed
          # This will also ignore the scroll wheel settings completely
          self.set_x_scale ( x_min, 0, x_max, w )
          self.set_y_scale ( y_min, 0, y_max, h )
        else:
          # Compute the proper scales and offsets to center the image
          # Note that positive scroll counts show a larger image, and negative scroll counts show a smaller image

          # Compute the slopes in x and y to fit exactly in each
          mx = w / float(x_max - x_min);
          my = h / float(y_max - y_min);

          # The desired scale will be just under the minimum of the slopes to keep the image square and in the window
          scale = 0.96 * min(mx,my);

          # This will be the new baseline so set the scroll_count and zoom_scale accordingly
          self.scroll_count = 0
          self.zoom_scale = 1.0

          # Compute the new width and height of points to be drawn in this scaled window
          width_of_points = int ( (x_max * scale) - (x_min * scale) );
          height_of_points = int ( (y_max * scale) - (y_min * scale) );

          # For centering, start with offsets = 0 and work back
          self.x_offset = 0;
          self.y_offset = 0;

          self.x_offset = - self.wxi(x_min);
          self.y_offset = - self.wyi(y_min);

          self.x_offset += (w - width_of_points) / 2;
          self.y_offset += (h - height_of_points) / 2;

          self.x_scale = scale
          self.y_scale = scale

      def zoom_at_point ( self, zoom_delta, at_x, at_y ):
        # First save the mouse location in user space before the zoom
        user_x_at_zoom = self.x(at_x)
        user_y_at_zoom = self.y(at_y)
        # Perform the zoom by changing the zoom scale
        self.scroll_count += zoom_delta
        #### Limit for now until image drawing can be optimized for large zooms:
        if self.scroll_count > self.max_zoom_count:
          self.scroll_count = self.max_zoom_count
        if self.scroll_count < self.min_zoom_count:
          self.scroll_count = self.min_zoom_count
        self.zoom_scale = pow (self.scroll_factor, self.scroll_count)
        # Get the new window coordinates of the previously saved user space location
        win_x_after_zoom = self.wx ( user_x_at_zoom )
        win_y_after_zoom = self.wy ( user_y_at_zoom )
        # Adjust the offsets (window coordinates) to keep user point at same location
        self.x_offset += at_x - win_x_after_zoom
        self.y_offset += at_y - win_y_after_zoom


      def get_drawing_area ( self ):
        return ( self.drawing_area )


      def queue_draw ( self ):
        return ( self.drawing_area.queue_draw() )


      def wx ( self, user_x ):
        return ( self.x_offset + (user_x * self.x_scale * self.zoom_scale ) )
      def wy ( self, user_y ):
        return ( self.y_offset + (user_y * self.y_scale * self.zoom_scale ) )
      def ww ( self, user_w ):
        return ( user_w * self.x_scale * self.zoom_scale )
      def wh ( self, user_h ):
        return ( user_h * self.y_scale * self.zoom_scale )

      def wxi ( self, user_x ):
        return ( int(round(self.wx(user_x))) )
      def wyi ( self, user_y ):
        return ( int(round(self.wy(user_y))) )
      def wwi ( self, user_w ):
        return ( int(round(self.ww(user_w))) )
      def whi ( self, user_h ):
        return ( int(round(self.wh(user_h))) )

      def x ( self, win_x ):
        return ( (win_x - self.x_offset) / (self.x_scale * self.zoom_scale) )
      def y ( self, win_y ):
        return ( (win_y - self.y_offset) / (self.y_scale * self.zoom_scale) )
      def w ( self, win_w ):
        return ( win_w / (self.x_scale * self.zoom_scale) )
      def h ( self, win_h ):
        return ( win_h / (self.y_scale * self.zoom_scale) )

      def set_cursor ( self, gtk_gdk_cursor ):
        self.drawing_area.window.set_cursor ( gtk.gdk.Cursor(gtk_gdk_cursor) )  # gtk.gdk.HAND2 DRAFT_SMALL TARGET HAND1 SB_UP_ARROW CROSS CROSSHAIR CENTER_PTR CIRCLE DIAMOND_CROSS IRON_CROSS PLUS CROSS_REVERSE DOT DOTBOX FLEUR


      def add_menu ( self, label ):
        menu = gtk.Menu()
        item = gtk.MenuItem(label)
        item.set_submenu ( menu )
        item.show()
        return (menu, item)

      def add_menu_item ( self, parent, callback, label, data, key=None, mask=gtk.gdk.CONTROL_MASK ):
        item = gtk.MenuItem(label=label)
        item.connect ( "activate", callback, data )
        if key != None:
          item.add_accelerator("activate", self.accel_group, ord(key), mask, gtk.ACCEL_VISIBLE)
        parent.append ( item )
        item.show()
        return ( item )

      def add_checkmenu_item ( self, parent, callback, label, data, key=None, mask=gtk.gdk.CONTROL_MASK, default=False ):
        item = gtk.CheckMenuItem(label=label)
        item.set_active ( default )
        item.connect ( "activate", callback, data )
        if key != None:
          item.add_accelerator("activate", self.accel_group, ord(key), mask, gtk.ACCEL_VISIBLE)
        parent.append ( item )
        item.show()
        return ( item )

      def add_radiomenu_item ( self, parent, callback, label, data, group=None, key=None, mask=gtk.gdk.CONTROL_MASK, default=False ):
        item = gtk.RadioMenuItem(group, label=label)
        item.set_active ( default )
        item.connect ( "activate", callback, data )
        if key != None:
          item.add_accelerator("activate", self.accel_group, ord(key), mask, gtk.ACCEL_VISIBLE)
        parent.append ( item )
        item.show()
        return ( item )

      def add_menu_sep ( self, parent ):
        item = gtk.SeparatorMenuItem()
        parent.append ( item )
        item.show()


      def mouse_scroll_callback ( self, canvas, event, zpa ):
        if event.direction == gtk.gdk.SCROLL_UP:
          zpa.zoom_at_point (  1, event.x, event.y )
        elif event.direction == gtk.gdk.SCROLL_DOWN:
          zpa.zoom_at_point ( -1, event.x, event.y )
        elif event.direction == gtk.gdk.SCROLL_LEFT:
          pass
        elif event.direction == gtk.gdk.SCROLL_RIGHT:
          pass
        else:
          pass
        zpa.drawing_area.queue_draw()
        return True  # Event has been handled, do not propagate further


      def button_press_callback ( self, widget, event, zpa ):
        # print ( "A mouse button was pressed at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
        if event.button == 1:
          #print ( "event.x = " + str(event.x) )
          zpa.last_x = event.x
          zpa.last_y = event.y
          zpa.dragging = True
        widget.queue_draw()
        return True  # Event has been handled, do not propagate further


      def button_release_callback ( self, widget, event, zpa ):
        # print ( "A mouse button was released at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
        if event.button == 1:
          #print ( "event.x = " + str(event.x) )
          zpa.x_offset += (event.x - zpa.last_x)
          zpa.y_offset += (event.y - zpa.last_y)
          zpa.last_x = event.x
          zpa.last_y = event.y
          zpa.dragging = False
        widget.queue_draw()
        return True  # Event has been handled, do not propagate further


      def mouse_motion_callback ( self, canvas, event, zpa ):
        # width, height = canvas.window.get_size()
        if event.state == 0:
          #print ( "Hover: x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
          pass
        elif event.state & gtk.gdk.BUTTON1_MASK:
          #print ( "Drag:  x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
          #__import__('code').interact(local = locals())
          #print ( "event.x = " + str(event.x) )
          zpa.x_offset += (event.x - zpa.last_x)
          zpa.y_offset += (event.y - zpa.last_y)
          zpa.last_x = event.x
          zpa.last_y = event.y
          canvas.queue_draw()

        return False  # Event has not been fully handled, allow to propagate further


      def key_press_callback ( self, widget, event, zpa ):
        # print ( "Key press event: " + str(event.keyval) + " = " + str(event) )
        handled = False
        if event.type == gtk.gdk.KEY_PRESS:
          # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
          #print ( "event.x = " + str(event.x) )
          if event.keyval == 65363:  # Right arrow: increase the x offset
            # print ("increasing offset from " + str(zpa.x_offset) )
            zpa.x_offset += -10
            # print ("                    to " + str(zpa.x_offset) )
          if event.keyval == 65361:  # Left arrow: decrease the x offset
            # print ("decreasing offset from " + str(zpa.x_offset) )
            zpa.x_offset += 10
            # print ("                    to " + str(zpa.x_offset) )
          if event.keyval == 65362:  # Up arrow: increase the y offset
            # print ("increasing offset from " + str(zpa.y_offset) )
            zpa.y_offset += 10
            # print ("                    to " + str(zpa.y_offset) )
          if event.keyval == 65364:  # Down arrow: decrease the y offset
            # print ("decreasing offset from " + str(zpa.y_offset) )
            zpa.y_offset += -10
            # print ("                    to " + str(zpa.y_offset) )
          widget.queue_draw()
          handled = True  # Event has been handled, do not propagate further
        return handled

    """
    def reset_callback(zpa):
      zpa.set_defaults()
      zpa.set_x_scale ( -1.0,   0, 1.0, 400 )
      zpa.set_y_scale (  0.0, 300, 1.0,   0 )
      drawing_area = zpa.get_drawing_area()
      drawing_area.queue_draw()
      return True
    """




# Import optional packages (mostly for plotting)

np = None
try:
  import numpy as np
except:
  print_debug ( 1, "Unable to plot without numpy" )
  np = None

sps = None
try:
  import scipy.stats as sps
except:
  print_debug ( 1, "Unable to plot without scipy.stats" )
  sps = None

plt = None
try:
  import matplotlib.pyplot as plt
except:
  print_debug ( 1, "Unable to plot without matplotlib" )
  plt = None


# Create one variable to check for plotting being available
global plotting_available
plotting_available = not ( None in (np, sps, plt) )

# Code common to GTK and Qt

global image_hbox
image_hbox = None

global zpa_original
zpa_original = None

global panel_list
panel_list = []

global global_win_width
global global_win_height
global_win_width = 600
global_win_height = 600

global alignment_layer_list
alignment_layer_list = []
global alignment_layer_index
alignment_layer_index = -1

global current_scale
current_scale = 1
global scales_dict
scales_dict = {}
scales_dict[current_scale] = alignment_layer_list

global project_file_name
project_file_name = ""

global project_path
project_path = None

global destination_path
destination_path = ""

global window
window = None

global menu_bar
menu_bar = None

global show_window_affines
show_window_affines = False

global show_window_centers
show_window_centers = False

global show_skipped_layers
show_skipped_layers = True

global point_mode
point_mode = False

global point_delete_mode
point_delete_mode = False

global point_cursor
point_cursor = gtk.gdk.CROSSHAIR

global max_image_file_size
max_image_file_size = 100000000

global generate_as_tiled
generate_as_tiled = False

global import_tiled
import_tiled = False

global show_tiled
show_tiled = False

global debug_level
debug_level = 10

def print_debug ( level, str ):
  global debug_level
  if level <= debug_level:
    print ( str )

global cursor_option_seps
cursor_option_seps = [2, 5, 7]

class gui_fields_class:
  ''' This class holds GUI widgets and not the persistent data. '''
  def __init__(self):
    # These values remain constant while scrolling through the stack
    self.proj_label = None
    self.dest_label = None
    self.num_align_forward = None
    self.jump_to_index = None
    self.snr_skip = None
    self.snr_halt = None
    self.code_base_select = None
    self.scales_list = [1]
    self.waves_dict = { 'R':50, 'C':50, 'A':0.01, 'F':5 }
    self.grid_dict = { 'N':10, 'ww':32 }

    # These values are swapped while scrolling through the stack
    self.trans_ww_entry = None
    self.trans_addx_entry = None
    self.trans_addy_entry = None
    self.skip_check_box = None
    self.align_method_select = None
    self.affine_check_box = None
    self.affine_ww_entry = None
    self.affine_addx_entry = None
    self.affine_addy_entry = None
    self.bias_check_box = None

    # These are different per layer, but maintained to be the same
    self.bias_dx_entry = None
    self.bias_dy_entry = None

    self.init_refine_apply_entry = None
    self.bias_rotation_entry = None
    self.bias_scale_x_entry = None
    self.bias_scale_y_entry = None
    self.bias_skew_x_entry = None


''' This variable gives global access to the GUI widgets '''
gui_fields = gui_fields_class()

alignment_opts = ["Init Affine", "Refine Affine", "Apply Affine"]

class graphic_primitive:
  ''' This base class defines something that can be drawn '''
  def __init__ ( self ):
    self.temp = False
    self.marker = False
    self.coordsys = 'p' # 'p' = Pixel Coordinates, 'i' = Image Coordinates, 's' = Scaled Coordinates (0.0 to 1.0)
    self.color = [1.0, 1.0, 1.0]
  def alloc_color ( self, colormap ):
    return colormap.alloc_color(int(65535*self.color[0]),int(65535*self.color[1]),int(65535*self.color[2]))
  def set_color_from_index ( self, i, mx=1 ):
    self.color = [mx*((i/(2**j))%2) for j in range(3)]
  def r10(self,x):
    return round(x*10)/10
  def jb ( self, bool_val ):
    if bool_val:
      return ( "true" )
    else:
      return ( "false" )
    return
  def from_json ( self, json_dict ):
    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    if 'type' in json_dict:
      if json_dict['type'] == 'dot':
        return graphic_dot ( json_dict['x'], json_dict['y'], json_dict['r'], json_dict['coordsys'], json_dict['color'], json_dict['group'] )
      elif json_dict['type'] == 'text':
        return graphic_text ( json_dict['x'], json_dict['y'], json_dict['s'], json_dict['coordsys'], json_dict['color'], json_dict['group'] )
      else:
        return graphic_text ( 10, 100, "Drawing not supported for type:" + json_dict['type'] )
    else:
      return graphic_text ( 10, 130, 'No type field in graphics item.' )


class graphic_line (graphic_primitive):
  def __init__ ( self, x1, y1, x2, y2, coordsys='i', color=[1.0,1.0,1.0], graphic_group="default" ):
    self.temp = False
    self.marker = False
    self.graphic_group = graphic_group
    self.x1 = x1
    self.y1 = y1
    self.x2 = x2
    self.y2 = y2
    self.coordsys = coordsys
    self.color = color
  def to_string ( self ):
    return ( "line (" + str(self.x1) + "," + str(self.y1) + ") to (" + str(self.x2) + "," + str(self.y2) + ")" )
  def to_json_string ( self ):
    return ( '{ "type":"line", "group":"' + str(self.graphic_group) + '", "x1":' + str(self.x1) + ', "y1":' + str(self.y1) + ', "x2":' + str(self.x2) + ', "y2":' + str(self.y2) + ', "coordsys":"' + str(self.coordsys) + '", "color":' + str(self.color) + ' }' )
  def draw ( self, zpa, drawing_area, pgl ):
    drawable = drawing_area.window
    colormap = drawing_area.get_colormap()
    gc = drawing_area.get_style().fg_gc[gtk.STATE_NORMAL]
    width, height = drawable.get_size()  # This is the area of the entire window
    #x, y = drawing_area.get_origin()
    old_fg = gc.foreground
    gc.foreground = self.alloc_color ( colormap )

    x1 = self.x1
    y1 = self.y1
    x2 = self.x2
    y2 = self.y2
    if self.coordsys == 'i':
      # Convert to image coordinates before drawing
      x1 = zpa.wxi(x1)
      y1 = zpa.wyi(y1)
      x2 = zpa.wxi(x2)
      y2 = zpa.wyi(y2)
    drawable.draw_line ( gc, x1,   y1,   x2,   y2   )
    drawable.draw_line ( gc, x1+1, y1,   x2+1, y2   )
    drawable.draw_line ( gc, x1,   y1+1, x2,   y2+1 )

    # Restore the previous color
    gc.foreground = old_fg
    return False


class graphic_rect (graphic_primitive):
  def __init__ ( self, x, y, dx, dy, coordsys='i', color=[1.0,1.0,1.0], graphic_group="default" ):
    self.temp = False
    self.marker = False
    self.graphic_group = graphic_group
    self.x = x
    self.y = y
    self.dx = dx
    self.dy = dy
    self.coordsys = coordsys
    self.color = color
  def to_string ( self ):
    return ( "rect (" + str(self.x1) + "," + str(self.y1) + ") to (" + str(self.x2) + "," + str(self.y2) + ")" )
  def to_json_string ( self ):
    return ( '{ "type":"rect", "group":"' + str(self.graphic_group) + '", "x":' + str(self.x1) + ', "y":' + str(self.y1) + ', "dx":' + str(self.dx) + ', "dy":' + str(self.dy) + ', "coordsys":"' + str(self.coordsys) + '", "color":' + str(self.color) + ' }' )
  def draw ( self, zpa, drawing_area, pgl ):
    drawable = drawing_area.window
    colormap = drawing_area.get_colormap()
    gc = drawing_area.get_style().fg_gc[gtk.STATE_NORMAL]
    width, height = drawable.get_size()  # This is the area of the entire window
    #x, y = drawing_area.get_origin()
    old_fg = gc.foreground
    gc.foreground = self.alloc_color ( colormap )

    x = self.x
    y = self.y
    dx = self.dx
    dy = self.dy
    if self.coordsys == 'i':
      # Convert to image coordinates before drawing
      x = zpa.wxi(x)
      y = zpa.wyi(y)
      dx = zpa.wwi(dx)
      dy = zpa.whi(dy)
    drawable.draw_rectangle ( gc, False, x, y, dx, dy )
    drawable.draw_rectangle ( gc, False, x-1, y-1, dx+2, dy+2 )
    drawable.draw_rectangle ( gc, False, x-2, y-2, dx+4, dy+4 )

    # Restore the previous color
    gc.foreground = old_fg
    return False


class graphic_marker (graphic_primitive):
  def __init__ ( self, x, y, r, coordsys='i', color=[1.0,1.0,1.0], graphic_group="default" ):
    self.temp = False
    self.marker = True
    self.graphic_group = graphic_group
    self.x = x
    self.y = y
    self.r = r
    self.coordsys = coordsys
    self.color = color
  def to_string ( self ):
    return ( "marker at (" + str(self.r10(self.x)) + "," + str(self.r10(self.y)) + ")" )
  def to_json_string ( self ):
    return ( '{ "type":"marker", "group":"' + str(self.graphic_group) + '", "x":' + str(self.x) + ', "y":' + str(self.y) + ', "r":' + str(self.r) + ', "coordsys":"' + str(self.coordsys) + '", "color":' + str(self.color) + ' }' )
  def draw ( self, zpa, drawing_area, pgl ):
    drawable = drawing_area.window
    colormap = drawing_area.get_colormap()
    gc = drawing_area.get_style().fg_gc[gtk.STATE_NORMAL]
    width, height = drawable.get_size()  # This is the area of the entire window
    #x, y = drawing_area.get_origin()
    old_fg = gc.foreground
    gc.foreground = self.alloc_color ( colormap )

    x = self.x
    y = self.y
    r = self.r
    if self.coordsys == 'i':
      # Convert to image coordinates before drawing
      x = zpa.wxi(x)
      y = zpa.wyi(y)
    drawable.draw_arc ( gc, False, x-r, y-r, 2*r, 2*r, 0, 360*64 )
    for d in range(5):
      rd = r+d
      drawable.draw_arc ( gc, False, x-rd, y-rd, 2*rd, 2*rd, 0, 360*64 )

    # Restore the previous color
    gc.foreground = old_fg
    return False


class graphic_dot (graphic_primitive):
  def __init__ ( self, x, y, r, coordsys='i', color=[1.0,1.0,1.0], graphic_group="default" ):
    self.temp = False
    self.marker = False
    self.graphic_group = graphic_group
    self.x = x
    self.y = y
    self.r = r
    self.coordsys = coordsys
    self.color = color
  def to_string ( self ):
    return ( "dot at (" + str(self.x) + "," + str(self.y) + "),r=" + str(self.r) )
  def to_json_string ( self ):
    return ( '{ "type":"dot", "group":"' + str(self.graphic_group) + '", "x":' + str(self.x) + ', "y":' + str(self.y) + ', "r":' + str(self.r) + ', "coordsys":"' + str(self.coordsys) + '", "color":' + str(self.color) + ' }' )
  def draw ( self, zpa, drawing_area, pgl ):
    drawable = drawing_area.window
    colormap = drawing_area.get_colormap()
    gc = drawing_area.get_style().fg_gc[gtk.STATE_NORMAL]
    width, height = drawable.get_size()  # This is the area of the entire window
    #x, y = drawing_area.get_origin()
    old_fg = gc.foreground
    gc.foreground = self.alloc_color ( colormap )

    x = self.x
    y = self.y
    r = self.r
    if self.coordsys == 'i':
      # Convert to image coordinates before drawing
      x = zpa.wxi(x)
      y = zpa.wyi(y)
    drawable.draw_arc ( gc, True, x-r, y-r, 2*r, 2*r, 0, 360*64 )

    # Restore the previous color
    gc.foreground = old_fg
    return False


class graphic_text (graphic_primitive):
  def __init__ ( self, x, y, s, coordsys='i', color=[1.0,1.0,1.0], graphic_group="default", temp=False ):
    self.temp = temp
    self.marker = False
    self.graphic_group = graphic_group
    self.x = x
    self.y = y
    self.s = s
    self.coordsys = coordsys
    self.color = color
  def to_string ( self ):
    return ( "text \"" + str(self.s) + "\" at (" + str(self.x) + "," + str(self.y) + ")" )
  def to_json_string ( self ):
    return ( '{ "type":"text", "group":"' + str(self.graphic_group) + '", "x":' + str(self.x) + ', "y":' + str(self.y) + ', "s":"' + str(self.s) + '", "coordsys":"' + str(self.coordsys) + '", "color":' + str(self.color) + ' }' )
  def draw ( self, zpa, drawing_area, pgl ):
    drawable = drawing_area.window
    colormap = drawing_area.get_colormap()
    gc = drawing_area.get_style().fg_gc[gtk.STATE_NORMAL]
    width, height = drawable.get_size()  # This is the area of the entire window
    #x, y = drawing_area.get_origin()
    old_fg = gc.foreground
    gc.foreground = self.alloc_color ( colormap )

    x = self.x
    y = self.y
    if self.coordsys == 'i':
      # Convert to image coordinates before drawing
      x = zpa.wxi(x)
      y = zpa.wyi(y)
    if self.coordsys == 's':
      # Convert to image coordinates before drawing
      x = int ( width * self.x )
      y = int ( height * self.y )
    pgl.set_text ( self.s )
    drawable.draw_layout ( gc, x, y, pgl )

    # Restore the previous color
    gc.foreground = old_fg
    return False



import struct

class tag_record:
  def __init__ ( self, tag, tagtype, tagcount, tagvalue ):
    self.tag = tag
    self.tagtype = tagtype
    self.tagcount = tagcount
    self.tagvalue = tagvalue
  def __repr__ ( self ):
    return ( "TR: " + str(self.tag) + ", " + str(self.tagtype) + ", " + str(self.tagcount) + ", " + str(self.tagvalue) )


class tiled_tiff:
  ''' This is an abstraction of a tiled tiff file to use for testing faster image display '''

  def __repr__ ( self ):
    tile_data_str = None
    f = open ( self.file_name, 'rb' )
    if len(self.tile_offsets) > 0:
      # Seek to the last one
      f.seek ( self.tile_offsets[0] )
      image_data = f.read ( self.tile_counts[0] )
      print_debug ( 1, "Read " + str(self.tile_counts[0]) + " bytes at " + str(self.tile_offsets[0]) + " from " + str(self.file_name) )

      # Print out a small corner of the tile:
      num_rows = self.tile_height
      num_cols = self.tile_width
      print_debug ( 1, '"' + str(num_cols) + ' ' + str(num_rows) + ' 256 2",' )
      color_table = []
      for n in range(256):
        color_table.append ( format(n,'02x') )
      for v in color_table:
        print_debug ( 1, '"' + v + ' c #' + v + v + v + '",' )

      for row in range(num_rows):
        pix_row = ""
        for col in range(num_cols):
          i = row * self.tile_width
          i += col
          pix_row += color_table[ord(image_data[i])]
        print_debug ( 1, '"' + pix_row + '",' )

      '''
      pix_list = [ color_table[ord(i)] for i in image_data[0:num_pix] ]
      #print_debug ( 1, "pix_list = " + str(pix_list) )

      pix_row = ""
      for i in range(len(pix_list)):
        pix_row += pix_list[i]
      print_debug ( 1, '"' + pix_row + '"' )
      tile_data_str = str([ord(d) for d in image_data[0:num_pix]])
      print_debug ( 1, "  " + tile_data_str )
      '''
    return ( "Done showing tiled_tiff" ) #tile_data_str )

  def __init__ ( self, file_name ):

    self.file_name = file_name
    self.endian = '<' # Intel format
    self.dir_record_list = []
    self.width = -1
    self.height = -1
    self.tile_width = -1
    self.tile_height = -1
    self.tile_offsets = []
    self.tile_counts = []

    self.pixbuf = None

    print_debug ( 1, "Reading from TIFF: " + str(file_name) )

    tag_record_list = []
    with open ( self.file_name, 'rb' ) as f:

      d = f.read(50)
      print_debug ( 1, "Tiff Data: " + str([ord(c) for c in d]) )
      f.seek(0)

      d = [ord(c) for c in f.read(4)] # Read 4 bytes of the header
      if   d == [0x49, 0x49, 0x2a, 0x00]:
        print_debug ( 1, "This is a TIFF file with Intel (little endian) byte ordering" )
        self.endian = '<' # Intel format
      elif d == [0x4d, 0x4d, 0x00, 0x2a]:
        print_debug ( 1, "This is a TIFF file with Motorola (big endian) byte ordering" )
        self.endian = '>' # Motorola format
      else:
        print_debug ( 1, "This is not a TIFF file" )
        self.endian = None
        return

      # Read the offset of the first image directory from the header
      offset = struct.unpack_from ( self.endian+"L", f.read(4), offset=0 )[0]
      print_debug ( 1, "Offset = " + str(offset) )

      dir_num = 1

      while offset > 0:
        f.seek ( offset )
        numDirEntries = struct.unpack_from ( self.endian+'H', f.read(2), offset=0 )[0]
        offset += 2
        print_debug ( 1, "Directory " + str(dir_num) + " has NumDirEntries = " + str(numDirEntries) )
        dir_num += 1
        # Read the tags
        f.seek ( offset )
        for tagnum in range(numDirEntries):
          tagtuple = struct.unpack_from ( self.endian+'HHLL', f.read(12), offset=0 )
          tag = tagtuple[0]
          tagtype = tagtuple[1]
          tagcount = tagtuple[2]
          tagvalue = tagtuple[3]
          tag_record_list.append ( tag_record ( tag, tagtype, tagcount, tagvalue ) )
          offset += 12
          tagstr = self.str_from_tag ( tagtuple )
          '''
          if tagstr.endswith ( 'ASCII' ):
            ascii_str = ":  \""
            for i in range(tagcount):
              try:
                ascii_str += str(struct.unpack_from ( self.endian+'s', f.read(2), offset=tagvalue+i )[0].decode('utf-8'))
              except:
                ascii_str += '?'
                f.seek ( tagvalue+i )
                print_debug ( 1, "     Decoding error for " + str(struct.unpack_from ( self.endian+'s', f.read(2), offset=tagvalue+i )[0]) + " in following tag:" )
            if len(ascii_str) > 60:
              ascii_str = ascii_str[0:60]
            ascii_str = ascii_str.replace ( "\n", " " )
            ascii_str = ascii_str.replace ( "\r", " " )
            tagstr += ascii_str + "\""
          '''
          print_debug ( 1, "  Tag = " + str(tagtuple) + " = " + tagstr )
        self.dir_record_list.append ( tag_record_list )
        tag_record_list = []
        f.seek ( offset )
        nextIFDOffset = struct.unpack_from ( self.endian+'L', f.read(4), offset=0 )[0]
        offset = nextIFDOffset
        print_debug ( 1, "\n" )

      print_debug ( 50, "\n\n" )
      print_debug ( 1, 120*"=" )
      print_debug ( 50, "\n\n" )


      dir_num = 1
      for dir_record in self.dir_record_list:
        print_debug ( 1, "Directory " + str(dir_num) + ":\n" )
        dir_num += 1
        bps = None
        w = None
        h = None
        tw = None
        tl = None
        to = None
        tc = None
        offsets = None
        counts = None
        for tag_rec in dir_record:
          print_debug ( 1, "  New tag: " + str(tag_rec) )
          if tag_rec.tag == 256:
            w = tag_rec.tagvalue
            self.width = w
            print_debug ( 1, "    Width: " + str(tag_rec.tagvalue) )
          if tag_rec.tag == 257:
            h = tag_rec.tagvalue
            self.height = h
            print_debug ( 1, "    Height: " + str(tag_rec.tagvalue) )
          if tag_rec.tag == 258:
            bps = tag_rec.tagvalue
            print_debug ( 1, "    Bits/Samp: " + str(tag_rec.tagvalue) )
            if bps != 8:
              print_debug ( 1, "Can't handle files with " + str(bps) + " bits per sample" )
              exit ( 0 )
          if tag_rec.tag == 322:
            tw = tag_rec.tagvalue
            self.tile_width = tw
            print_debug ( 1, "    TileWidth: " + str(tag_rec.tagvalue) )
          if tag_rec.tag == 323:
            tl = tag_rec.tagvalue
            self.tile_height = tl
            print_debug ( 1, "    TileLength: " + str(tag_rec.tagvalue) )
          if tag_rec.tag == 324:
            to = tag_rec.tagvalue
            print_debug ( 1, "    TileOffsets: " + str(tag_rec.tagvalue) )
            f.seek ( tag_rec.tagvalue )
            offsets = struct.unpack_from ( self.endian+(tag_rec.tagcount*"L"), f.read(4*tag_rec.tagcount), offset=0 )
            self.tile_offsets = offsets
            print_debug ( 1, "       " + str(offsets) )
          if tag_rec.tag == 325:
            tc = tag_rec.tagvalue
            print_debug ( 1, "    TileByteCounts: " + str(tag_rec.tagvalue) )
            f.seek ( tag_rec.tagvalue )
            counts = struct.unpack_from ( self.endian+(tag_rec.tagcount*"L"), f.read(4*tag_rec.tagcount), offset=0 )
            self.tile_counts = counts
            print_debug ( 1, "       " + str(counts) )

        if not (None in (bps, w, h, tw, tl, to, tc)):
          print_debug ( 1, "\nRead from a block of tiles ...\n" )
          for i in range(len(offsets)):
            offset = offsets[i]
            count = counts[i]
            f.seek ( offset )
            data = struct.unpack_from ( self.endian+"BBBB", f.read(4), offset=0 )
            #print_debug ( 1, "Read data " + str(data) + " from " + str(offset) )
            #print_debug ( 1, "" )
        '''
        if not (None in (bps, w, h, tw, tl, to, tc)):
          print_debug ( 1, "\nFound a block of tiles:\n" )
          for i in range(len(offsets)):
            offset = offsets[i]
            count = counts[i]
            f.seek ( offset )
            data = struct.unpack_from ( self.endian+(count*"B"), f.read(count), offset=0 )
            for r in range(tl):
              print_debug ( 1, str ( [ data[(r*tw)+d] for d in range(tw) ] ) )
            print_debug ( 1, "" )
        '''

        # offset = 0 ############ Force a stop


      print_debug ( 50, "\n\n" )

  def get_tile_data_as_xpm ( self, tile_row, tile_col ):

    print_debug ( 1, "Inside get_tile_data_as_xpm" )

    xpm_strings = []

    tile_data_str = None
    f = open ( self.file_name, 'rb' )
    if len(self.tile_offsets) > 0:
      # Seek to the first one
      f.seek ( self.tile_offsets[0] )
      image_data = f.read ( self.tile_counts[0] )
      print_debug ( 1, "Read " + str(self.tile_counts[0]) + " bytes at " + str(self.tile_offsets[0]) + " from " + str(self.file_name) )

      # Convert the tile data to XPM format:

      num_rows = self.tile_height
      num_cols = self.tile_width
      xpm_strings.append ( str(num_cols) + ' ' + str(num_rows) + ' 256 2' )

      color_table = []
      for n in range(256):
        color_table.append ( format(n,'02x') )
      for v in color_table:
        xpm_strings.append ( v + ' c #' + v + v + v )

      for row in range(num_rows):
        pix_row = ""
        for col in range(num_cols):
          i = row * self.tile_width
          i += col
          pix_row += color_table[ord(image_data[i])]
        xpm_strings.append ( pix_row )

    return ( xpm_strings )


  def get_tile_data_as_pixbuf ( self, tile_row, tile_col ):
    if self.pixbuf == None:
      self.pixbuf = gtk.gdk.pixbuf_new_from_xpm_data ( self.get_tile_data_as_xpm ( tile_row, tile_col ) )
    return ( self.pixbuf )


  def is_immediate ( self, tagtuple ):
    tag = tagtuple[0]
    tagtype = tagtuple[1]
    tagcount = tagtuple[2]
    tagvalue = tagtuple[3]
    if tagtype == 1:
      # Byte
      return (tagcount <= 4)
    elif tagtype == 2:
      # ASCII null-terminated string
      # Assume that this is never in the tag?
      return False
    elif tagtype == 3:
      # Short (2-byte)
      return (tagcount <= 2)
    elif tagtype == 4:
      # Long (4-byte)
      return (tagcount <= 1)
    elif tagtype == 5:
      # Rational (2 long values)
      return False
    elif tagtype == 6:
      # Signed Byte
      return (tagcount <= 4)
    elif tagtype == 7:
      # Undefined Byte
      return (tagcount <= 4)
    elif tagtype == 8:
      # Signed Short
      return (tagcount <= 2)
    elif tagtype == 9:
      # Signed Long
      return (tagcount <= 1)
    elif tagtype == 10:
      # Signed Rational (2 long signed)
      return False
    elif tagtype == 11:
      # Float (4 bytes)
      return (tagcount <= 1)
    elif tagtype == 12:
      # Double (8 bytes)
      return false


  def str_from_tag ( self, t ):
    global bigend

    dtype = "Unknown"
    if t[1] == 1:
      dtype = "Byte"
    elif t[1] == 2:
      dtype = "ASCII"
    elif t[1] == 3:
      dtype = "Short"
    elif t[1] == 4:
      dtype = "Long"
    elif t[1] == 5:
      dtype = "Rational"

    elif t[1] == 6:
      dtype = "SByte"
    elif t[1] == 7:
      dtype = "UNDEF Byte"
    elif t[1] == 8:
      dtype = "SShort"
    elif t[1] == 9:
      dtype = "SLong"
    elif t[1] == 10:
      dtype = "SRational"
    elif t[1] == 11:
      dtype = "Float"
    elif t[1] == 12:
      dtype = "Double"

    dlen = str(t[2])

    tagid = None

    if t[0] == 256:
      tagid = "Width"
    elif t[0] == 257:
      tagid = "Height"
    elif t[0] == 258:
      tagid = "BitsPerSample"
    elif t[0] == 259:
      tagid = "Compression"
    elif t[0] == 262:
      tagid = "PhotoMetInterp"
    elif t[0] == 266:
      tagid = "FillOrder"
    elif t[0] == 275:
      tagid = "Orientation"
    elif t[0] == 277:
      tagid = "SampPerPix"
    elif t[0] == 278:
      tagid = "RowsPerStrip"
    elif t[0] == 282:
      tagid = "XResolution"
    elif t[0] == 283:
      tagid = "YResolution"
    elif t[0] == 322:
      tagid = "TileWidth"
    elif t[0] == 323:
      tagid = "TileLength"
    elif t[0] == 274:
      tagid = "Orientation"
    elif t[0] == 254:
      tagid = "NewSubFileType"
    elif t[0] == 284:
      tagid = "T4Options"
    elif t[0] == 292:
      tagid = "PlanarConfig"
    elif t[0] == 296:
      tagid = "ResolutionUnit"
    elif t[0] == 297:
      tagid = "PageNumber"
    elif t[0] == 317:
      tagid = "Predictor"
    elif t[0] == 318:
      tagid = "WhitePoint"
    elif t[0] == 319:
      tagid = "PrimChroma"
    elif t[0] == 324:
      tagid = "TileOffsets"
    elif t[0] == 325:
      tagid = "TileByteCounts"
    elif t[0] == 323:
      tagid = "TileLength"
    elif t[0] == 322:
      tagid = "TileWidth"
    elif t[0] == 338:
      tagid = "ExtraSamples"
    elif t[0] == 530:
      tagid = "YCbCrSubSampling"
    elif t[0] == 273:
      tagid = "StripOffsets"
    elif t[0] == 279:
      tagid = "StripByteCounts"
    elif t[0] == 305:
      tagid = "Software"
    elif t[0] == 306:
      tagid = "DateTime"
    elif t[0] == 320:
      tagid = "ColorMap"
    elif t[0] == 339:
      tagid = "SampleFormat"

    if tagid is None:
      tagid = "?????????"

    return ( tagid + " ... " + dlen + " of " + dtype )



class annotated_image:
  ''' An image with a series of drawing primitives defined in
      the pixel coordinates of the image. '''
  def __init__ ( self, file_name=None, clone_from=None, role=None ):
    # Initialize everything to defaults
    self.file_name = file_name
    self.file_size = -1
    self.image = None
    self.tiled_image = None
    self.graphics_items = []
    self.role = role
    # self.results_dict = None

    # Copy in the clone if provided
    if type(clone_from) != type(None):
      self.file_name = clone_from.file_name
      self.image = clone_from.image
      self.tiled_image = clone_from.tiled_image
      self.graphics_items = [ gi for gi in clone_from.graphics_items ]

    # Over-ride other items as provided
    if type(file_name) != type(None):
      self.file_name = file_name
    if role != None:
      self.role = role
    if (type(self.image) == type(None)) and (type(self.file_name) != type(None)):
      try:
        f = file ( self.file_name )
        f.seek (0, 2)
        self.file_size = f.tell()
        f.close()
        global max_image_file_size
        if self.file_size < max_image_file_size:
          global gtk_mode
          if gtk_mode:
            print ( "Loading GTK file from " + str(self.file_name) )
            self.image = gtk.gdk.pixbuf_new_from_file ( self.file_name )
          else:
            print ( "Loading QT file from " + str(self.file_name) )
            self.image = QPixmap ( self.file_name )
          print_debug ( 50, "Loaded " + str(self.file_name) )
        else:
          self.image = None
          print_debug ( -1, "File " + str(self.file_name) + " (" + str(self.file_size) + " bytes) is too large to load." )
          self.graphics_items.insert ( 0, graphic_text(0.4, 0.5, "File Size: " + str(self.file_size), coordsys='s', color=[1, 0.5, 0.5], temp=True) )
      except Exception as e:
        print ( "Exception caught while showing window centers: " + str(e) )
        print_debug ( -1, "Got an exception in annotated_image constructor reading annotated image " + str(self.file_name) )
        print_debug ( -1, "Exception: " + str(e) )
        # exit(1)
        self.image = None

    if (type(self.tiled_image) == type(None)) and (type(self.file_name) != type(None)):
      if os.path.splitext(self.file_name)[1] == ".ttif":
        # Read in the structure for a tiled_tiff image
        self.tiled_image = tiled_tiff ( self.file_name )

    if type(clone_from) == type(None):
      self.add_file_name_graphic()

  def to_string ( self ):
    return ( "AnnoImage \"" + str(self.file_name) + "\" with annotations: " + str([gi.to_string() for gi in self.graphics_items]) )

  def use_image_from ( self, other_annotated_image ):
    self.file_name = other_annotated_image.file_name
    self.image = other_annotated_image.image
    self.tiled_image = other_annotated_image.tiled_image
    self.add_file_name_graphic()

  def add_file_name_graphic ( self ):
    if type(self.file_name) != type(None):
      self.graphics_items.insert ( 0, graphic_text(100, 2, self.file_name.split('/')[-1], coordsys='p', color=[1, 1, 1]) )

  def set_role ( self, role ):
    self.role = role

  def get_marker_points ( self ):
    point_list = []
    for item in self.graphics_items:
      if item.marker:
        point_list.append ( [item.x, item.y] )
    return point_list

  def clear_non_marker_graphics ( self ):
    marker_list = [ gi for gi in self.graphics_items if gi.marker ]
    self.graphics_items = marker_list

  def add_graphic ( self, item ):
    self.graphics_items.append ( item )


class alignment_layer:
  ''' An alignment_layer has a base image and a set of images and processes representing the relationships to its neighbors '''
  def __init__ ( self, base=None ):
    print_debug ( 50, "Constructing new alignment_layer with base " + str(base) )
    self.base_image_name = base
    self.align_proc = None
    self.align_method = 0
    self.align_method_text = 'Auto Swim Align'

    # This holds a single annotated image
    self.base_annotated_image = None

    # This holds the annotated images to be stored and/or displayed.
    self.image_dict = {}

    # These are the parameters used for this layer
    self.trans_ww = 256
    self.trans_addx = 256
    self.trans_addy = 256

    self.skip = False
    self.snr_skip = False

    self.affine_enabled = True
    self.affine_ww = 256
    self.affine_addx = 256
    self.affine_addy = 256

    self.bias_enabled = True
    self.bias_dx = 0.0
    self.bias_dy = 0.0

    self.init_refine_apply = 'Init Affine'
    self.bias_rotation = 0.0
    self.bias_scale_x = 0.0
    self.bias_scale_y = 0.0
    self.bias_skew_x = 0.0

    # This holds whatever is produced by this alignment
    self.results_dict = {}

    try:
      self.base_annotated_image = annotated_image ( self.base_image_name, role="base" )
      # By default, the first (and only) image in the list will be the base image
    except:
      self.base_annotated_image = annotated_image ( None, role="base" )

    # Always initialize with the image
    self.image_dict['base'] = self.base_annotated_image

    global show_tiled
    self.tile_data = None
    if show_tiled:
      print_debug ( 1, "Creating an alignment_layer with tiling enabled" )
      self.tile_data = tiled_tiff ( self.base_image_name )


  def to_string ( self ):
    s = "AlignLayer \"" + str(self.base_image_name) + "\" with images:"
    for k,v in self.image_dict.items():
      s = s + "\n  " + str(k) + ": " + v.to_string()
    return ( s )



# These two global functions are handy for callbacks

def store_fields_into_current_layer():
  if (alignment_layer_list != None) and (alignment_layer_index >= 0):
    if alignment_layer_index < len(alignment_layer_list):
      a = alignment_layer_list[alignment_layer_index]
      a.trans_ww = int(gui_fields.trans_ww_entry.get_text())
      a.trans_addx = int(gui_fields.trans_addx_entry.get_text())
      a.trans_addy = int(gui_fields.trans_addy_entry.get_text())
      a.skip = gui_fields.skip_check_box.get_active()
      a.align_method      = gui_fields.align_method_select.get_active()
      a.align_method_text = gui_fields.align_method_select.get_active_text()
      a.affine_enabled = gui_fields.affine_check_box.get_active()
      a.affine_ww = int(gui_fields.affine_ww_entry.get_text())

      a.affine_addx = int(gui_fields.affine_addx_entry.get_text())
      a.affine_addy = int(gui_fields.affine_addy_entry.get_text())
      a.bias_enabled = gui_fields.bias_check_box.get_active()
      print_debug ( 70, "Storing 1, a.bias_dx = " + str(a.bias_dx) )
      a.bias_dx = float(gui_fields.bias_dx_entry.get_text())
      a.bias_dy = float(gui_fields.bias_dy_entry.get_text())
      print_debug ( 70, "Storing 2, a.bias_dx = " + str(a.bias_dx) )


      a.init_refine_apply = gui_fields.init_refine_apply_entry.get_active_text()
      a.bias_rotation = float(gui_fields.bias_rotation_entry.get_text())
      a.bias_scale_x = float(gui_fields.bias_scale_x_entry.get_text())
      a.bias_scale_y = float(gui_fields.bias_scale_y_entry.get_text())
      a.bias_skew_x = float(gui_fields.bias_skew_x_entry.get_text())

      # Store the bias values in all layers to give them a "global" feel
      # If the final version needs individual biases, just comment this code:
      if alignment_layer_list != None:
        if len(alignment_layer_list) > 0:
          for t in alignment_layer_list:
            t.bias_dx = a.bias_dx
            t.bias_dy = a.bias_dy
            t.init_refine_apply = a.init_refine_apply
            t.bias_rotation = a.bias_rotation
            t.bias_scale_x = a.bias_scale_x
            t.bias_scale_y = a.bias_scale_y
            t.bias_skew_x = a.bias_skew_x

      print_debug ( 70, "Storing 3, a.bias_dx = " + str(a.bias_dx) )


def store_current_layer_into_fields():
  if (alignment_layer_list != None) and (alignment_layer_index >= 0):
    if alignment_layer_index < len(alignment_layer_list):
      a = alignment_layer_list[alignment_layer_index]
      print_debug ( 50, " Index = " + str(alignment_layer_index) + ", base_name_ann = " + a.base_annotated_image.file_name )
      print_debug ( 50, "  trans_ww = " + str(a.trans_ww) + ", trans_addx = " + str(a.trans_addx) + ", trans_addy = " + str(a.trans_addy) )
      gui_fields.trans_ww_entry.set_text ( str(a.trans_ww) )
      gui_fields.trans_addx_entry.set_text ( str(a.trans_addx) )
      gui_fields.trans_addy_entry.set_text ( str(a.trans_addy) )
      gui_fields.skip_check_box.set_active ( a.skip )
      gui_fields.align_method_select.set_active ( a.align_method )
      # gui_fields.align_method_select.set_active_text ( a.align_method_text )
      gui_fields.affine_check_box.set_active ( a.affine_enabled )
      gui_fields.affine_ww_entry.set_text ( str(a.affine_ww) )

      gui_fields.affine_addx_entry.set_text(str(a.affine_addx))
      gui_fields.affine_addy_entry.set_text(str(a.affine_addy))
      gui_fields.bias_check_box.set_active(a.bias_enabled)
      print_debug ( 70, "store_current_layer_into_fields for " + str(alignment_layer_index) + " with bias_dx = " + str(a.bias_dx) )
      gui_fields.bias_dx_entry.set_text(str(a.bias_dx))
      gui_fields.bias_dy_entry.set_text(str(a.bias_dy))

      # TODO gui_fields.init_refine_apply_entry.set_text(str(a.init_refine_apply))
      gui_fields.init_refine_apply_entry.set_active ( alignment_opts.index(a.init_refine_apply) )
      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      gui_fields.bias_rotation_entry.set_text(str(a.bias_rotation))
      gui_fields.bias_scale_x_entry.set_text(str(a.bias_scale_x))
      gui_fields.bias_scale_y_entry.set_text(str(a.bias_scale_y))
      gui_fields.bias_skew_x_entry.set_text(str(a.bias_skew_x))



class zoom_panel ( app_window.zoom_pan_area ):
  '''zoom_panel - provide a drawing area that can be zoomed and panned.'''
  global gui_fields
  global panel_list
  global gtk_mode

  def __init__ ( self, window, win_width, win_height, role="", point_add_enabled=False ):

    self.panel_dict = {}
    self.role = role
    self.point_add_enabled = point_add_enabled
    self.force_center = False

    # Call the constructor for the parent app_window.zoom_pan_area:
    app_window.zoom_pan_area.__init__ ( self, window, win_width, win_height, role )

    # Connect the scroll event for the drawing area (from zoom_pan_area) to a local function:
    self.drawing_area.connect ( "scroll_event", self.mouse_scroll_callback, self )
    self.drawing_area.connect ( "key_press_event", self.key_press_callback, self )
    #self.drawing_area.connect ( "button_press_event", self.button_press_callback, self )

    # Create a "pango_layout" which seems to be needed for drawing text
    self.pangolayout = window.create_pango_layout("")
    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


  def button_press_callback ( self, canvas, event, zpa ):
    global alignment_layer_list
    global alignment_layer_index
    if self.point_add_enabled:
      if point_mode and not point_delete_mode:
        print_debug ( 50, "Got a button press in point mode at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
        print_debug ( 50, "  Image coordinates: " + str(self.x(event.x)) + "," + str(self.y(event.y)) )

        #  print_debug ( 50, "Adding a marker point to the original image" )
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        this_image = alignment_layer_list[alignment_layer_index].image_dict[self.role]
        print_debug ( 50, "    Storing point in layer " + str(alignment_layer_index) + ", for role " + str(self.role) )
        # if this_image.point_add_enabled:
        if self.point_add_enabled:
          this_image.graphics_items.append ( graphic_marker(self.x(event.x),self.y(event.y),6,'i',[1, 0, 0]) )

      if point_delete_mode:
        print_debug ( 50, "Got a button press in point delete mode at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )

        this_image = alignment_layer_list[alignment_layer_index].image_dict[self.role]

        image_click_x = self.x(event.x)
        image_click_y = self.y(event.y)

        closest_x = 0
        closest_y = 0
        closest_dist = sys.float_info.max
        marker_list = [ item for item in this_image.graphics_items if item.marker ]
        closest_marker = None
        for gi in marker_list:
          print_debug ( 50, "Clicked at " + str(image_click_x) + "," + str(image_click_y) + ", marker at : " + str(gi.x) + "," + str(gi.y) )
          this_dist = math.pow(image_click_x-gi.x, 2) + math.pow(image_click_y-gi.y, 2)
          if this_dist < closest_dist:
            closest_x = gi.x
            closest_y = gi.y
            closest_dist = this_dist
            closest_marker = gi
        print_debug ( 50, "Closest pt = " + str(closest_x) + "," + str(closest_y) )
        if math.sqrt(closest_dist) < 20:
          print_debug ( 50, "Removing the point" )
          this_image.graphics_items.remove ( closest_marker )

        print_debug ( 50, "  Image coordinates: " + str(self.x(event.x)) + "," + str(self.y(event.y)) )

        print_debug ( 50, "    Deleting point in layer " + str(alignment_layer_index) + ", for role " + str(self.role) )
        # print_debug ( 50, "image has " + str(len(this_image.graphics_items)) + " items" )
        for gi in [ x for x in this_image.graphics_items if x.marker ]:
          print_debug ( 50, "Item " + str(gi.to_string()) )
        # if this_image.point_add_enabled:
        #if self.point_add_enabled:
        #  this_image.graphics_items.append ( graphic_marker(self.x(event.x),self.y(event.y),6,'i',[1, 0, 0]) )

      # Draw the windows
      zpa_original.queue_draw()
      for p in panel_list:
        p.queue_draw()


    # print_debug ( 50, "pyswift_gui: A mouse button was pressed at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
    if 'GDK_SHIFT_MASK' in event.get_state().value_names:
      # Do any special processing for shift click
      # Print the mouse location in screen coordinates:
      print_debug ( 50, "pyswift_gui: A mouse button was pressed at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
      # Print the mouse location in image coordinates:
      print_debug ( 50, "pyswift_gui:   Image coordinates: " + str(self.x(event.x)) + "," + str(self.y(event.y)) )
      # return ( app_window.zoom_pan_area.button_press_callback ( self, canvas, event, zpa ) )
      return True # Event has been handled
    else:
      # Call the parent's function to handle the click
      return ( app_window.zoom_pan_area.button_press_callback ( self, canvas, event, zpa ) )
    return True  # Event has been handled, do not propagate further

  def button_release_callback ( self, canvas, event, zpa ):
    #print_debug ( 50, "A mouse button was released at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
    return ( app_window.zoom_pan_area.button_release_callback ( self, canvas, event, zpa ) )

  def move_through_stack ( self, direction ):
    global alignment_layer_list
    global alignment_layer_index
    global show_skipped_layers

    # Store the alignment_layer parameters into the image layer being exited
    store_fields_into_current_layer()

    if show_skipped_layers:
      # Move to the next image layer (potentially)
      alignment_layer_index += direction
      if direction > 0:
        if alignment_layer_index >= len(alignment_layer_list):
          alignment_layer_index =  len(alignment_layer_list)-1
      elif direction < 0:
        if alignment_layer_index < 0:
          alignment_layer_index = 0
    else:
      # Move to the next non-skipped image layer (potentially)
      unskipped = [ i for i in range(len(alignment_layer_list)) if alignment_layer_list[i].skip == False ]
      print_debug ( 50, "Unskipped indexes: " + str(unskipped) )
      if len(unskipped) > 0:
        if direction > 0:
          next_index = -1
          for u in unskipped:
            if u > alignment_layer_index:
              next_index = u
              break
          if next_index >= 0:
            # There was a next index, so use it
            alignment_layer_index = next_index
        elif direction < 0:
          next_index = -1
          unskipped.reverse()
          for u in unskipped:
            if u < alignment_layer_index:
              next_index = u
              break
          if next_index >= 0:
            # There was a next index, so use it
            alignment_layer_index = next_index
        else: # direction == 0
          # Move to the closest layer
          print_debug ( 50, "Finding closest unskipped layer ..." )
          closest_index = -1
          closest_dist = 100 * len(alignment_layer_list)
          for u in unskipped:
            dist = abs(alignment_layer_index - u)
            if dist < closest_dist:
              closest_index = u
              closest_dist = dist
          alignment_layer_index = closest_index

    # Display the alignment_layer parameters from the new section being viewed
    if alignment_layer_index >= 0:
      store_current_layer_into_fields()


  def mouse_scroll_callback ( self, canvas, event, zpa ):
    ''' Overload the base mouse_scroll_callback to provide custom UNshifted action. '''

    if 'GDK_SHIFT_MASK' in event.get_state().value_names:
      # Use shifted scroll wheel to zoom the image size
      return ( app_window.zoom_pan_area.mouse_scroll_callback ( self, canvas, event, zpa ) )
    else:
      # Use normal (unshifted) scroll wheel to move through the stack

      global alignment_layer_list
      global alignment_layer_index
      print_debug ( 50, "Moving through the stack with alignment_layer_index = " + str(alignment_layer_index) )
      if len(alignment_layer_list) <= 0:
        alignment_layer_index = -1
        print_debug ( 60, " Index = " + str(alignment_layer_index) )
      else:
        if event.direction == gtk.gdk.SCROLL_UP:
          self.move_through_stack ( 1 )
        elif event.direction == gtk.gdk.SCROLL_DOWN:
          self.move_through_stack ( -1 )

        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      # Draw the windows
      zpa_original.queue_draw()
      for p in panel_list:
        p.queue_draw()
      return True

  def mouse_motion_callback ( self, canvas, event, zpa ):
    ''' Overload the base mouse_motion_callback when shifted '''
    if 'GDK_SHIFT_MASK' in event.get_state().value_names:
      # Ignore the event
      return False
    else:
      # Call the parent's function to handle the motion
      return ( app_window.zoom_pan_area.mouse_motion_callback ( self, canvas, event, zpa ) )

  def key_press_callback ( self, widget, event, zpa ):
    print_debug ( 50, "Key press event: " + str(event.keyval) + " = " + str(event) )
    handled = False
    if (event.type == gtk.gdk.KEY_PRESS) and (event.keyval in [65362,65364]):  # Up arrow: increase the y offset
      print_debug ( 50, "Arrow key" )
      if event.keyval == 65362:  # Up arrow: Move
        self.move_through_stack ( 1 )
      if event.keyval == 65364:  # Down arrow: Move
        self.move_through_stack ( -1 )
      widget.queue_draw()
      # Draw the windows
      zpa_original.queue_draw()
      for p in panel_list:
        p.queue_draw()
      handled = True  # Event has been handled, do not propagate further
    else:
      handled = app_window.zoom_pan_area.key_press_callback ( self, widget, event, zpa )
    return handled

  def expose_callback ( self, drawing_area, event, zpa ):
    ''' Draw all the elements in this window '''
    if self.force_center:
      center_all_images()
      self.force_center = False
    x, y, width, height = event.area  # This is the area of the portion newly exposed
    width, height = drawing_area.window.get_size()  # This is the area of the entire window
    x, y = drawing_area.window.get_origin()
    drawable = drawing_area.window
    colormap = drawing_area.get_colormap()
    gc = drawing_area.get_style().fg_gc[gtk.STATE_NORMAL]
    # Save the current color
    old_fg = gc.foreground
    # Clear the screen with black
    gc.foreground = colormap.alloc_color(0,0,0)
    drawable.draw_rectangle(gc, True, 0, 0, width, height)

    global alignment_layer_list
    global alignment_layer_index
    global show_window_centers
    global show_window_affines
    global show_skipped_layers
    global show_tiled

    # print_debug ( 50, "Painting with len(alignment_layer_list) = " + str(len(alignment_layer_list)) )

    pix_buf = None
    if len(alignment_layer_list) > 0:
      # Draw one of the images
      if alignment_layer_index < len(alignment_layer_list):
        im_dict = alignment_layer_list[alignment_layer_index].image_dict
        if self.role in im_dict:
          pix_buf = im_dict[self.role].image
          if show_tiled and not (im_dict[self.role].tiled_image is None):
            ti = im_dict[self.role].tiled_image
            pix_buf = ti.get_tile_data_as_pixbuf ( 0, 0 )


    if pix_buf != None:
      pbw = pix_buf.get_width()
      pbh = pix_buf.get_height()
      scale_w = zpa.ww(pbw) / pbw
      scale_h = zpa.wh(pbh) / pbh

      # The following chunk of code was an attempt
      #   to only draw the part of the image that
      #   is showing in the window. In the Java
      #   version, the code simply calculates the
      #   two corners of the image in screen space,
      #   and requests that it be drawn. The Java
      #   drawing API knows to clip the image as
      #   needed and does so very efficiently. But
      #   GTK (at least in this version) is very
      #   inefficient, and the drawing performance
      #   declines very rapidly as the image is
      #   zoomed in. At some point, the application
      #   effectively locks up. This is fine for
      #   early testing, but will need to be fixed
      #   eventually. One possible solution is to
      #   use a newer version of GTK. That may fix
      #   it with no changes (as the Java version).
      #   If not, the following code may be needed
      #   as a starting point to clip out the part
      #   of the image to be drawn and draw it to
      #   the proper window coordinates.

      ##scaled_image = pix_buf.scale_simple( int(pbw*scale_w), int(pbh*scale_h), gtk.gdk.INTERP_BILINEAR )
      #scaled_image = pix_buf.scale_simple( int(pbw*scale_w), int(pbh*scale_h), gtk.gdk.INTERP_NEAREST )
      #drawable.draw_pixbuf ( gc, scaled_image, 0, 0, zpa.wxi(0), zpa.wyi(0), -1, -1, gtk.gdk.RGB_DITHER_NONE )

      #(dw,dh) = drawable.get_size()
      #pbcs = pix_buf.get_colorspace()
      # dest_pm = gtk.gdk.Pixmap ( drawable, dw, dh )
      #dest = gtk.gdk.Pixbuf ( pbcs, False, drawable.get_depth(), dw, dh )
      #dest = gtk.gdk.Pixbuf ( pbcs, False, 8, dw, dh )  # For some reason the depth seems to have to be 8
      #pix_buf.scale(dest, 0, 0, 10, 10, 0, 0, 1, 1, gtk.gdk.INTERP_NEAREST)
      #drawable.draw_pixbuf ( gc, scaled_image, 0, 0, zpa.wxi(0), zpa.wyi(0), -1, -1, gtk.gdk.RGB_DITHER_NONE )

      #gtk.gdk

      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      # Note: The Java code scales the image as it is drawn and doesn't create large images as is done here.
      #       However, the Python call ("gdk_draw_pixbuf") doesn't provide a scaling term (see call below).
      #
      #   The scale_simple call can create huge images that quickly overwhelm the available memory.
      #   This code should be re-written to scale only the portion of the image to actually be rendered.
      #
      #   It should likely use "scale" rather than "scale_simple":
      #     (from https://developer.gnome.org/gdk-pixbuf/stable/gdk-pixbuf-Scaling.html#gdk-pixbuf-scale-simple)
      #
      #      gdk_pixbuf_scale_simple (const GdkPixbuf *src,  // a GdkPixbuf - in Python, this is the object itself
      #                        int dest_width,               // the width of the region to render
      #                        int dest_height,              // the height of the region to render
      #                        GdkInterpType interp_type);   // the interpolation type for the transformation.
      #
      #      gdk_pixbuf_scale (const GdkPixbuf *src,   // a GdkPixbuf - in Python, this is the object itself
      #                        GdkPixbuf *dest,        // the GdkPixbuf into which to render the results
      #                        int dest_x,             // the left coordinate for region to render
      #                        int dest_y,             // the top coordinate for region to render
      #                        int dest_width,         // the width of the region to render
      #                        int dest_height,        // the height of the region to render
      #                        double offset_x,        // the offset in the X direction (currently rounded to an integer)
      #                        double offset_y,        // the offset in the Y direction (currently rounded to an integer)
      #                        double scale_x,         // the scale factor in the X direction
      #                        double scale_y,         // the scale factor in the Y direction
      #                        GdkInterpType interp_type); // the interpolation type for the transformation.
      #
      #      (from https://developer.gnome.org/gdk2/stable/gdk2-Drawing-Primitives.html#gdk-draw-pixbuf)
      #      gdk_draw_pixbuf (GdkDrawable *drawable,   // a GdkDrawable - in Python, this is the drawable object itself
      #                       GdkGC *gc,               // a GdkGC, used for clipping, or NULL.
      #                       const GdkPixbuf *pixbuf, // a GdkPixbuf
      #                       gint src_x,              // Source X coordinate within pixbuf.
      #                       gint src_y,              // Source Y coordinates within pixbuf.
      #                       gint dest_x,             // Destination X coordinate within drawable.
      #                       gint dest_y,             // Destination Y coordinate within drawable.
      #                       gint width,              // Width of region to render, in pixels, or -1 to use pixbuf width.
      #                       gint height,             // Height of region to render, in pixels, or -1 to use pixbuf height.
      #                       GdkRgbDither dither,     // Dithering mode for GdkRGB.
      #                       gint x_dither,           // X offset for dither.
      #                       gint y_dither);          // Y offset for dither.

      """
      def draw_pixbuf(gc, pixbuf, src_x, src_y, dest_x, dest_y, width=-1, height=-1, dither=gtk.gdk.RGB_DITHER_NORMAL, x_dither=0, y_dither=0)

        gc : a gtk.gdk.GC, used for clipping, or None
        pixbuf : a gtk.gdk.Pixbuf
        src_x : Source X coordinate within pixbuf.
        src_y : Source Y coordinate within pixbuf.
        dest_x : Destination X coordinate within drawable.
        dest_y : Destination Y coordinate within drawable.
        width : Width of region to render, in pixels, or -1 to use pixbuf width. Must be specified in PyGTK 2.2.
        height : Height of region to render, in pixels, or -1 to use pixbuf height. Must be specified in PyGTK 2.2
        dither : Dithering mode for GdkRGB.
        x_dither : X offset for dither.
        y_dither : Y offset for dither.

      The draw_pixbuf() method renders a rectangular portion of a gtk.gdk.Pixbuf specified by pixbuf
      to the drawable using the gtk.gdk.GC specified by gc. The portion of pixbuf that is rendered is
      specified by the origin point (src_x src_y) and the width and height arguments. pixbuf is rendered
      to the location in the drawable specified by (dest_x dest_y). dither specifies the dithering mode a
      s one of:

        gtk.gdk.RGB_DITHER_NONE 	  Never use dithering.

        gtk.gdk.RGB_DITHER_NORMAL   Use dithering in 8 bits per pixel (and below) only.

        gtk.gdk.RGB_DITHER_MAX	    Use dithering in 16 bits per pixel and below.

      The destination drawable must have a colormap. All windows have a colormap, however, pixmaps only have
      colormap by default if they were created with a non-None window argument. Otherwise a colormap must be
      set on them with the gtk.gdk.Drawable.set_colormap() method.

      On older X servers, rendering pixbufs with an alpha channel involves round trips to the X server, and
      may be somewhat slow. The clip mask of gc is ignored, but clip rectangles and clip regions work fine.

      ========
      https://developer.gnome.org/gdk-pixbuf/stable/gdk-pixbuf-Scaling.html
      C:
      void gdk_pixbuf_scale (const GdkPixbuf *src,
                    GdkPixbuf *dest,
                    int dest_x,
                    int dest_y,
                    int dest_width,
                    int dest_height,
                    double offset_x,
                    double offset_y,
                    double scale_x,
                    double scale_y,
                    GdkInterpType interp_type);
      Python:
         src.scale ( dest, dest_x, dest_y, dest_width, dest_height, offset_x, offset_y, scale_x, scale_y, interp_type )
            src          a GdkPixbuf
            dest         the GdkPixbuf into which to render the results
            dest_x       the left coordinate for region to render
            dest_y       the top coordinate for region to render
            dest_width   the width of the region to render
            dest_height  the height of the region to render
            offset_x     the offset in the X direction (currently rounded to an integer)
            offset_y     the offset in the Y direction (currently rounded to an integer)
            scale_x      the scale factor in the X direction
            scale_y      the scale factor in the Y direction
            interp_type  the interpolation type for the transformation.
      """
      try:
        scale_to_w = int(pbw*scale_w)
        scale_to_h = int(pbh*scale_h)
        if scale_to_w * scale_to_h > 0:
          # print_debug ( 50, "Scaling with " + str(int(pbw*scale_w)) + " " + str(int(pbh*scale_h)) )
          scaled_image = pix_buf.scale_simple( int(pbw*scale_w), int(pbh*scale_h), gtk.gdk.INTERP_NEAREST )
          drawable.draw_pixbuf ( gc, scaled_image, 0, 0, zpa.wxi(0), zpa.wyi(0), -1, -1, gtk.gdk.RGB_DITHER_NONE )
      except:
        pass

    # Draw any annotations in the list
    if len(alignment_layer_list) > 0:
      # Draw annotations
      if alignment_layer_index < len(alignment_layer_list):
        im_dict = alignment_layer_list[alignment_layer_index].image_dict
        if self.role in im_dict:
          image_to_draw = im_dict[self.role]
          color_index = 0
          for graphics_item in image_to_draw.graphics_items:
            if graphics_item.marker:
              color_index += 1
              graphics_item.set_color_from_index ( color_index )
              graphics_item.draw ( zpa, drawing_area, self.pangolayout )
            else:
              if graphics_item.graphic_group == 'default':
                graphics_item.draw ( zpa, drawing_area, self.pangolayout )
              elif (graphics_item.graphic_group == 'Centers') and show_window_centers:
                graphics_item.draw ( zpa, drawing_area, self.pangolayout )
              elif (graphics_item.graphic_group == 'Affines') and show_window_affines:
                graphics_item.draw ( zpa, drawing_area, self.pangolayout )
          if alignment_layer_list[alignment_layer_index].skip:
            # Draw the skipped X
            gc.foreground = colormap.alloc_color(65535,0,0)
            for delta in range(-10,11):
              if delta >= 0:
                drawable.draw_line ( gc, 0+delta, 0, width, height-delta ) # upper left to lower right
                drawable.draw_line ( gc, 0, height-delta, width-delta, 0 ) # lower left to upper right
              else:
                drawable.draw_line ( gc, 0, 0-delta, width+delta, height ) # upper left to lower right
                drawable.draw_line ( gc, 0-delta, height, width, 0-delta ) # lower left to upper right
          elif alignment_layer_list[alignment_layer_index].snr_skip:
            # Draw the SNR skipped /
            gc.foreground = colormap.alloc_color(65535,65535,0)
            for delta in range(-6,7):
              if delta >= 0:
                # drawable.draw_line ( gc, 0+delta, 0, width, height-delta ) # upper left to lower right
                drawable.draw_line ( gc, 0, height-delta, width-delta, 0 ) # lower left to upper right
              else:
                # drawable.draw_line ( gc, 0, 0-delta, width+delta, height ) # upper left to lower right
                drawable.draw_line ( gc, 0-delta, height, width, 0-delta ) # lower left to upper right


    # Draw a separator between the panes
    gc.foreground = colormap.alloc_color(32767,32767,32767)
    drawable.draw_line ( gc, 0, 0, 0, height )
    drawable.draw_line ( gc, width-1, 0, width-1, height )

    # Draw this window's role
    gc.foreground = colormap.alloc_color(65535,65535,32767)
    if str(self.role) == str('base'):
      # Special case to change "base" to "src"
      self.pangolayout.set_text ( str('src')+":" )
    else:
      self.pangolayout.set_text ( str(self.role)+":" )
    drawable.draw_layout ( gc, 3, 2, self.pangolayout )
    # Draw the current scale
    global current_scale
    self.pangolayout.set_text ( str(current_scale) )
    drawable.draw_layout ( gc, 10, 22, self.pangolayout )

    # Restore the previous color
    gc.foreground = old_fg
    return False


def set_all_or_fwd_callback ( set_all ):
  if set_all:
    print_debug ( 50, "Setting All ..." )
  else:
    print_debug ( 50, "Setting Forward ..." )
  global alignment_layer_list
  global alignment_layer_index
  if alignment_layer_list != None:
    if len(alignment_layer_list) > 0:
      template = alignment_layer_list[alignment_layer_index]

      # Store the current values from the gui into the template structure
      template.trans_ww = int(gui_fields.trans_ww_entry.get_text())
      template.trans_addx = int(gui_fields.trans_addx_entry.get_text())
      template.trans_addy = int(gui_fields.trans_addy_entry.get_text())
      template.skip = gui_fields.skip_check_box.get_active()
      template.align_method      = gui_fields.align_method_select.get_active()
      template.align_method_text = gui_fields.align_method_select.get_active_text()
      template.affine_enabled = gui_fields.affine_check_box.get_active()
      template.affine_ww = int(gui_fields.affine_ww_entry.get_text())
      template.affine_addx = int(gui_fields.affine_addx_entry.get_text())
      template.affine_addy = int(gui_fields.affine_addy_entry.get_text())
      template.bias_enabled = gui_fields.bias_check_box.get_active()
      template.bias_dx = float(gui_fields.bias_dx_entry.get_text())
      template.bias_dy = float(gui_fields.bias_dy_entry.get_text())

      # Copy the template into all other sections as appropriate
      copy = False
      for a in alignment_layer_list:
        if set_all or (a == template):
          copy = True
        if copy and (a != template):
          # print_debug ( 50, "Copying " + str(a) )
          a.trans_ww = template.trans_ww
          a.trans_addx = template.trans_addx
          a.trans_addy = template.trans_addy
          # a.skip = template.skip
          # a.align_method = template.align_method
          a.affine_enabled = template.affine_enabled
          a.affine_ww = template.affine_ww
          a.affine_addx = template.affine_addx
          a.affine_addy = template.affine_addy
          a.bias_enabled = template.bias_enabled
          a.bias_dx = template.bias_dx
          a.bias_dy = template.bias_dy

  return True


def change_skip_callback(zpa):
  global gui_fields
  print_debug ( 50, "Skip Changed!!" )
  print_debug ( 50, "State is now " + str(gui_fields.skip_check_box.get_active()) )

  if alignment_layer_list[alignment_layer_index].skip != gui_fields.skip_check_box.get_active():

    print_debug ( 50, "This is an actual change in the value for a layer rather than simply a change of layer" )
    # This is an actual change in the value for a layer rather than simply a change of layer (which also triggers the change_skip_callback)
    alignment_layer_list[alignment_layer_index].skip = gui_fields.skip_check_box.get_active()

    # Calculate the unskipped regions before and after this layer:
    unskipped_before = [ i for i in range(0,alignment_layer_index) if alignment_layer_list[i].skip == False ]
    prev_unskipped_index = None
    if len(unskipped_before) > 0:
      prev_unskipped_index = unskipped_before[-1]
    print_debug ( 50, "Unskipped before this layer = " + str(unskipped_before) )
    unskipped_after = [ i for i in range(alignment_layer_index+1,len(alignment_layer_list)) if alignment_layer_list[i].skip == False ]
    next_unskipped_index = None
    if len(unskipped_after) > 0:
      next_unskipped_index = unskipped_after[0]
    print_debug ( 50, "Unskipped after this layer = " + str(unskipped_after) )

    # Fix the connections between layers given the state of this skip after changing

    if alignment_layer_list[alignment_layer_index].skip:
      # This image wasn't skipped before but is being skipped now
      if (type(prev_unskipped_index) != type(None)) and (type(next_unskipped_index) != type(None)):
        # Connect the previous unskipped to the next unskipped
        alignment_layer_list[next_unskipped_index].image_dict['ref'] = annotated_image ( clone_from=alignment_layer_list[prev_unskipped_index].image_dict['base'], role='ref' )
        # alignment_layer_list[alignment_layer_index].image_dict['ref'] = annotated_image()
    else:
      # This image was skipped before but is being unskipped now
      if type(prev_unskipped_index) != type(None):
        # Connect the previous unskipped image to this image
        alignment_layer_list[alignment_layer_index].image_dict['ref'] = annotated_image ( clone_from=alignment_layer_list[prev_unskipped_index].image_dict['base'], role='ref' )
      if type(next_unskipped_index) != type(None):
        # Connect the this image to the next unskipped
        alignment_layer_list[next_unskipped_index].image_dict['ref'] = annotated_image ( clone_from=alignment_layer_list[alignment_layer_index].image_dict['base'], role='ref' )

  # zpa.queue_draw()
  for p in panel_list:
    p.move_through_stack ( 0 )
    p.drawing_area.queue_draw()

  # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
  return True

def step_callback(zpa):
  zpa.get_drawing_area().queue_draw()
  return True


def step_in_callback(zpa):
  zpa.get_drawing_area().queue_draw()
  return True


def background_callback ( zpa ):
  if zpa.user_data['running']:
    t = time.time()
  return True


def add_panel_callback ( zpa, role="", point_add_enabled=False ):
  print_debug ( 70, "Adding a panel with role " + str(role) )
  print_debug ( 50, "Add a Panel" )
  global image_hbox
  global panel_list
  global window


  new_panel = zoom_panel(window,global_win_width,global_win_height,role=role,point_add_enabled=point_add_enabled)
  new_panel.force_center = True

  new_panel.user_data = {
                    'image_frame'        : None,
                    'image_frames'       : [],
                    'frame_number'       : -1,
                    'running'            : False,
                    'last_update'        : -1,
                    'show_legend'        : True,
                    'frame_delay'        : 0.1,
                    'size'               : 1.0
                  }

  # Set the relationships between "user" coordinates and "screen" coordinates

  new_panel.set_x_scale ( 0.0, 300, 100.0, 400 )
  new_panel.set_y_scale ( 0.0, 250 ,100.0, 350 )

  # The zoom/pan area has its own drawing area (that it zooms and pans)
  new_panel_drawing_area = new_panel.get_drawing_area()

  # Add the zoom/pan area to the vertical box (becomes the main area)
  image_hbox.pack_start(new_panel_drawing_area, True, True, 0)

  new_panel_drawing_area.show()

  # The zoom/pan area doesn't draw anything, so add our custom expose callback
  new_panel_drawing_area.connect ( "expose_event", new_panel.expose_callback, new_panel )

  # Set the events that the zoom/pan area must respond to
  #  Note that zooming and panning requires button press and pointer motion
  #  Other events can be set and handled by user code as well
  new_panel_drawing_area.set_events ( gtk.gdk.EXPOSURE_MASK
                                   | gtk.gdk.LEAVE_NOTIFY_MASK
                                   | gtk.gdk.BUTTON_PRESS_MASK
                                   | gtk.gdk.POINTER_MOTION_MASK
                                   | gtk.gdk.POINTER_MOTION_HINT_MASK )

  panel_list.append ( new_panel )
  return True


def rem_panel_callback ( zpa ):
  print_debug ( 50, "Remove a Panel" )
  global image_hbox
  global window
  global panel_list

  if len(panel_list) > 1:
    image_hbox.remove(panel_list[-1].drawing_area)
    panel_list.pop ( -1 )
    return True

  return False


def jump_to_callback ( zpa ):
  global alignment_layer_list
  global alignment_layer_index
  global gui_fields
  global panel_list
  global zpa_original

  # Store the alignment_layer parameters into the image layer being exited
  store_fields_into_current_layer()

  if len(alignment_layer_list) <= 0:
    alignment_layer_index = -1
  else:
    index_str = gui_fields.jump_to_index.get_text()
    if len(index_str.strip()) > 0:
      # A jump location has been entered
      try:
        jump_index = int(index_str.strip())
        if jump_index < 0:
          jump_index = 0
        if (jump_index >= len(alignment_layer_list)):
          jump_index = len(alignment_layer_list)-1
        alignment_layer_index = jump_index
      except:
        print_debug ( 50, "The jump index should be an integer and not " + index_str )

  # Display the alignment_layer parameters from the new section being viewed
  store_current_layer_into_fields()
  zpa_original.queue_draw()
  for p in panel_list:
    p.queue_draw()

def snr_skip_to_skip_callback ( flag ):
  # Copy all of the snr_skip values into skip values

  global alignment_layer_list
  if alignment_layer_list != None:
    if len(alignment_layer_list) > 0:
      for a in alignment_layer_list:
        a.skip = a.snr_skip
    store_current_layer_into_fields()
  zpa_original.queue_draw()
  for p in panel_list:
    p.queue_draw()
  return True


def clear_all_skips_callback ( flag ):
  # Clear all of the snr_skip flags

  global alignment_layer_list
  if alignment_layer_list != None:
    if len(alignment_layer_list) > 0:
      for a in alignment_layer_list:
        a.skip = False
    store_current_layer_into_fields()
  zpa_original.queue_draw()
  for p in panel_list:
    p.queue_draw()
  return True


def clear_snr_skip_to_skip_callback ( flag ):
  # Clear all of the snr_skip flags

  global alignment_layer_list
  if alignment_layer_list != None:
    if len(alignment_layer_list) > 0:
      for a in alignment_layer_list:
        a.snr_skip = False
    store_current_layer_into_fields()
  zpa_original.queue_draw()
  for p in panel_list:
    p.queue_draw()
  return True


import thread

import align_swiftir

class StringBufferFile:
  def __init__ ( self ):
    self.fs = ""
  def write ( self, s ):
    self.fs = self.fs + s

def fstring ( fval ):
  if math.isnan(fval):
    return ( "NaN" )
  return str(fval)

def write_json_project ( project_file_name, fb=None ):

  # Update the data layer(s) from the current fields before writing!
  store_fields_into_current_layer()

  global project_path
  # global project_file_name
  global destination_path
  global zpa_original
  global alignment_layer_list
  global alignment_layer_index
  global panel_list

  global max_image_file_size

  global point_cursor
  global cursor_options
  global point_mode
  global point_delete_mode

  global gui_fields

  global scales_dict

  if len(project_file_name) > 0:
    # Actually write the file
    gui_fields.proj_label.set_text ( "Project File: " + str(project_file_name) )
    rel_dest_path = ""
    if len(destination_path) > 0:
      rel_dest_path = os.path.relpath(destination_path,start=project_path)

    f = None
    if fb is None:
      # This is the default to write to a file
      print_debug ( 50, "Saving destination path = " + str(destination_path) )
      f = open ( project_file_name, 'w' )
    else:
      # Since a file buffer (fb) was provided, write to it rather than a file
      print_debug ( 50, "Writing to string" )
      f = fb

    f.write ( '{\n' )
    f.write ( '  "version": 0.2,\n' )
    f.write ( '  "method": "SWiFT-IR",\n' )

    f.write ( '  "user_settings": {\n' )
    f.write ( '    "max_image_file_size": ' + str(max_image_file_size) + '\n' )
    f.write ( '  },\n' )

    global current_plot_code
    if len(current_plot_code.strip()) > 0:
      print_debug ( 1, "Saving custom plot code" )
      code_p = pickle.dumps ( current_plot_code, protocol=0 )
      code_e = base64.b64encode ( code_p )
      sl = 40
      code_l = [ code_e[sl*s:(sl*s)+sl] for s in range(1+(len(code_e)/sl)) ]
      f.write ( '  "plot_code": [\n' )
      for s in code_l:
        f.write ( '    "' + s + '",\n' )
      f.write ( '    ""\n' )
      f.write ( '  ],\n' )

    f.write ( '  "data": {\n' )
    f.write ( '    "source_path": "",\n' )
    f.write ( '    "destination_path": "' + str(rel_dest_path).replace('\\','/') + '",\n' )
    f.write ( '    "pairwise_alignment": true,\n' )
    f.write ( '    "defaults": {\n' )
    f.write ( '      "align_to_next_pars": {\n' )
    f.write ( '        "window_size": 1024,\n' )
    f.write ( '        "addx": 800,\n' )
    f.write ( '        "addy": 800,\n' )
    f.write ( '        "bias_x_per_image": 0.0,\n' )
    f.write ( '        "bias_y_per_image": 0.0,\n' )
    f.write ( '        "output_level": 0\n' )
    f.write ( '      }\n' )
    f.write ( '    },\n' )
    f.write ( '    "current_scale": ' + str(current_scale) + ',\n' )
    f.write ( '    "current_layer": ' + str(alignment_layer_index) + ',\n' )

    f.write ( '    "scales": {\n' )

    last_scale_key = 1
    if len(scales_dict.keys()) > 0:
      last_scale_key = sorted(scales_dict.keys())[-1]

    for scale_key in sorted(scales_dict.keys()):

      align_layer_list_for_scale = scales_dict[scale_key]

      f.write ( '      "' + str(scale_key) + '": {\n' )
      if align_layer_list_for_scale != None:
        if len(align_layer_list_for_scale) > 0:
          f.write ( '        "alignment_stack": [\n' )
          for a in align_layer_list_for_scale:
            f.write ( '          {\n' )
            f.write ( '            "skip": ' + str(a.skip).lower() + ',\n' )
            if a != align_layer_list_for_scale[-1]:
              # Not sure what to leave out for last image ... keep all for now
              pass
            f.write ( '            "images": {\n' )

            img_keys = sorted(a.image_dict.keys(), reverse=True)
            for k in img_keys:
              im = a.image_dict[k]
              #print_debug ( 90, "    " + str(k) + " alignment points: " + str(im.get_marker_points()) )
              f.write ( '              "' + k + '": {\n' )  # "base": {
              # rel_file_name = os.path.relpath(a.base_image_name,start=project_path)
              print_debug ( 90, "Try to get relpath for " + str(im.file_name) + " starting at " + str(project_path) )
              rel_file_name = ""
              if type(im.file_name) != type(None):
                rel_file_name = os.path.relpath(im.file_name,start=project_path)
              f.write ( '                "filename": "' + rel_file_name.replace('\\','/') + '",\n' )
              f.write ( '                "metadata": {\n' )
              f.write ( '                  "match_points": ' + str(im.get_marker_points()) + ',\n' )
              if len(im.graphics_items) <= 0:
                f.write ( '                  "annotations": []\n' )
              else:
                f.write ( '                  "annotations": [\n' )
                # Filter out the markers which are handled in other code
                non_marker_list = [ gi for gi in im.graphics_items if not gi.marker ]
                # Filter out any temporary annotations
                non_marker_list = [ gi for gi in non_marker_list if not gi.temp ]
                # Only output the non-markers being careful not to add a trailing comma
                for gi_index in range(len(non_marker_list)):
                  gi = non_marker_list[gi_index]
                  f.write ( "                    " + gi.to_json_string().replace('\\','/') )
                  if gi_index < (len(non_marker_list)-1):
                    f.write ( ',\n' )
                  else:
                    f.write ( '\n' )
                f.write ( '                  ]\n' )
              f.write ( '                }\n' )
              if k != img_keys[-1]:
                f.write ( '              },\n' )
              else:
                f.write ( '              }\n' )
            f.write ( '            },\n' )
            f.write ( '            "align_to_ref_method": {\n' )
            f.write ( '              "selected_method": "' + str(a.align_method_text) + '",\n' )
            f.write ( '              "method_options": ["Auto Swim Align", "Match Point Align"],\n' )
            f.write ( '              "method_data": {\n' )
            f.write ( '                "alignment_options": [' + ', '.join ( ['"'+o+'"' for o in alignment_opts] ) + '],\n' )
            f.write ( '                "alignment_option": "' + str(a.init_refine_apply) + '",\n' )
            f.write ( '                "window_size": ' + str(a.trans_ww) + ',\n' )
            f.write ( '                "addx": ' + str(a.trans_addx) + ',\n' )
            f.write ( '                "addy": ' + str(a.trans_addy) + ',\n' )
            f.write ( '                "bias_x_per_image": ' + fstring(a.bias_dx) + ',\n' )
            f.write ( '                "bias_y_per_image": ' + fstring(a.bias_dy) + ',\n' )
            f.write ( '                "bias_scale_x_per_image": ' + fstring(a.bias_scale_x) + ',\n' )
            f.write ( '                "bias_scale_y_per_image": ' + fstring(a.bias_scale_y) + ',\n' )
            f.write ( '                "bias_skew_x_per_image": ' + fstring(a.bias_skew_x) + ',\n' )
            f.write ( '                "bias_rot_per_image": ' + fstring(a.bias_rotation) + ',\n' )
            f.write ( '                "output_level": 0\n' )
            f.write ( '              },\n' )
            f.write ( '              "method_results": {\n' )
            #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

            if type(a.results_dict) != type(None):
              if 'affine' in a.results_dict:
                smat = str(a.results_dict['affine'])
                smat = smat.replace ( 'nan', 'NaN' )
                f.write ( '                "affine_matrix": ' + smat + ',\n' )
              if 'cumulative_afm' in a.results_dict:
                smat = str(a.results_dict['cumulative_afm'])
                smat = smat.replace ( 'nan', 'NaN' )
                f.write ( '                "cumulative_afm": ' + smat + ',\n' )
              if 'snr' in a.results_dict:
                f.write ( '                "snr": ' + fstring(a.results_dict['snr']) + '\n' )
            f.write ( '              }\n' )
            f.write ( '            }\n' )
            if a != align_layer_list_for_scale[-1]:
              f.write ( '          },\n' )
            else:
              f.write ( '          }\n' )
          f.write ( '        ]\n' )
          if scale_key != last_scale_key:
            f.write ( '      },\n' )
          else:
            f.write ( '      }\n' )

    f.write ( '    }\n' ) # "scales": {

    f.write ( '  }\n' ) # "data": {

    f.write ( '}\n' ) # End of entire dictionary


def str2D ( m ):
  # Ensure that a 2D matrix is "flat"
  s = '['
  for r in m:
    s = s + ' ['
    for c in r:
      s = s + ' ' + str("%.3f"%c)
    s = s + ' ]'
  s = s + ' ]'
  return ( s )


def setup_initial_panels():

  global panel_list
  # Set up the preferred panels as needed
  ref_panel = None
  base_panel = None
  aligned_panel = None

  # Remove all windows to force desired arrangement
  #print_debug ( 50, "Note: deleting all windows to force preferred" )
  #while len(panel_list) > 0:
  #  rem_panel_callback ( zpa_original )

  # Start by assigning any panels with roles already set
  for panel in panel_list:
    if panel.role == 'ref':
      ref_panel = panel
    if panel.role == 'base':
      base_panel = panel
    if panel.role == 'aligned':
      aligned_panel = panel

  # Assign any empty panels if needed
  for panel in panel_list:
    if panel.role == '':
      if ref_panel == None:
        panel.role = 'ref'
        ref_panel = panel
      elif base_panel == None:
        panel.role = 'base'
        base_panel = panel
      elif aligned_panel == None:
        panel.role = 'aligned'
        aligned_panel = panel

  # Finally add panels as needed
  if ref_panel == None:
    add_panel_callback ( zpa_original, role='ref', point_add_enabled=True )
  if base_panel == None:
    add_panel_callback ( zpa_original, role='base', point_add_enabled=True )
  if aligned_panel == None:
    add_panel_callback ( zpa_original, role='aligned', point_add_enabled=False )

  # The previous logic hasn't worked, so force all panels to be as desired for now
  forced_panel_roles = ['ref', 'base', 'aligned']
  for i in range ( min ( len(panel_list), len(forced_panel_roles) ) ):
    panel_list[i].role = forced_panel_roles[i]



def run_alignment_callback ( align_all ):
  global debug_level
  global alignment_layer_list
  global alignment_layer_index
  global destination_path
  global gui_fields
  global panel_list
  global project_file_name

  print_debug ( 20, "\n" )
  print_debug ( 10, "\n\nStart Alignment" )

  store_fields_into_current_layer()

  if len(destination_path) == 0:
    dest_err_dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK, message_format="Destination not set.")
    response = dest_err_dialog.run()
    dest_err_dialog.destroy()
    return


  scale_dest_path = os.path.join(destination_path, "scale_"+str(current_scale), "img_aligned")
  print_debug ( 50, "\n\n scale_dest_path = " + scale_dest_path + "\n\n" )

  #########################################################
  #########################################################
  ## This panel setup might be better in the runner?
  #########################################################
  #########################################################

  setup_initial_panels()

  print_debug ( 40, "Running with " + str(gui_fields.code_base_select.get_active_text()) )

  if str(gui_fields.code_base_select.get_active_text()) == "External Swim Align":

    #########################################################
    #########################################################
    ## Call the known external runner
    #########################################################
    #########################################################

    # Write out the JSON file and run the currently hard-coded script to align it
    write_json_project ( "run_project.json" )
    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
    module = __import__ ( "pyswift_run_external" )
    # module.main()
    num_forward = None
    num_forward_str = gui_fields.num_align_forward.get_text()
    if len(num_forward_str.strip()) > 0:
      # A forward limit has been entered
      try:
        num_forward = int(num_forward_str.strip())
      except:
        num_forward = None

    snr_skip = None
    snr_skip_str = gui_fields.snr_skip.get_text()
    if len(snr_skip_str.strip()) > 0:
      # An snr_skip limit has been entered
      try:
        snr_skip = float(snr_skip_str.strip())
      except:
        print_debug ( 1, "The SNR Skip value should be a number and not " + snr_skip_str )

    snr_halt = None
    snr_halt_str = gui_fields.snr_halt.get_text()
    if len(snr_halt_str.strip()) > 0:
      # An snr_halt limit has been entered
      try:
        snr_halt = float(snr_halt_str.strip())
      except:
        print_debug ( 1, "The SNR Halt value should be a number and not " + snr_halt_str )

    module.run_alignment ( align_all,
                           alignment_layer_list,
                           alignment_layer_index,
                           num_forward,
                           snr_skip,
                           snr_halt,
                           scale_dest_path,
                           panel_list,
                           project_file_name )


  elif str(gui_fields.code_base_select.get_active_text()) == "Internal Swim Align":

    #########################################################
    #########################################################
    ## Call the internal runner
    #########################################################
    #########################################################

    # Create a list of alignment pairs accounting for skips, start point, and number to align

    align_pairs = []  # List of images to align with each other, a repeated index means copy directly to the output (a "golden section")
    last_ref = -1
    for i in range(len(alignment_layer_list)):
      print_debug ( 50, "Aligning with method " + str(alignment_layer_list[i].align_method) + " = " + alignment_layer_list[i].align_method_text )
      if alignment_layer_list[i].skip == False:
        if last_ref < 0:
          # This image was not skipped, but their is no previous, so just copy to itself
          align_pairs.append ( [i, i, alignment_layer_list[i].align_method] )
        else:
          # There was a previously unskipped image and this image is unskipped
          # Therefore, add this pair to the list
          align_pairs.append ( [last_ref, i, alignment_layer_list[i].align_method] )
        # This unskipped image will always become the last unskipped (reference) for next unskipped
        last_ref = i
      else:
        # This should just remove those image_dict items that shouldn't show when skipped
        alignment_layer_list[i].image_dict['aligned'] = annotated_image(None, role='aligned')

    print_debug ( 50, "Full list after removing skips:" )
    for apair in align_pairs:
      print_debug ( 50, "  Alignment pair: " + str(apair) )

    if not align_all:
      # Retain only those pairs that start after this index
      if alignment_layer_index == 0:
        # Include the current layer to make the original copy again
        new_pairs = [ p for p in align_pairs if p[1] >= alignment_layer_index ]
      else:
        # Exclude the current layer
        new_pairs = [ p for p in align_pairs if p[1] >= alignment_layer_index ]
      align_pairs = new_pairs
      # Remove any pairs beyond the number forward
      num_forward_str = gui_fields.num_align_forward.get_text()
      if len(num_forward_str.strip()) > 0:
        # A forward limit has been entered
        try:
          num_forward = int(num_forward_str.strip())
          new_pairs = [ p for p in align_pairs if p[1] < alignment_layer_index+num_forward ]
          align_pairs = new_pairs
        except:
          print_debug ( 50, "The number forward should be an integer and not " + num_forward_str )

    print_debug ( 50, "Full list after removing start and forward limits:" )
    for apair in align_pairs:
      print_debug ( 50, "  Alignment pair: " + str(apair) )

    for apair in align_pairs:
      i = apair[0] # Reference
      j = apair[1] # Current moving
      m = apair[2] # Alignment Method (0=SwimWindow, 1=MatchPoint)
      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      print_debug ( 50, "===============================================================================" )
      print_debug ( 50, "Aligning base:" + str(j) + " to ref:" + str(i) + " with method " + str(m) + " using:" )
      print_debug ( 50, "" )
      print_debug ( 50, "  method                   = " + str(['Auto Swim Align', 'Match Point Align'][m]) )
      print_debug ( 50, "  ref                     = " + str(alignment_layer_list[i].base_image_name) )
      print_debug ( 50, "  base                   = " + str(alignment_layer_list[j].base_image_name) )
      print_debug ( 50, "  skip                     = " + str(alignment_layer_list[j].skip) )
      print_debug ( 50, "" )
      print_debug ( 50, "  Image List for Layer " + str(i) + " contains:" + str(sorted(alignment_layer_list[i].image_dict.keys(), reverse=True)) )
      # Tom: print_debug ( 50, "  Image List for Layer " + str(j) + " contains:" + str(sorted(alignment_layer_list[j].image_dict.keys(), reverse=True)) )
      for k in sorted(alignment_layer_list[j].image_dict.keys(), reverse=True):
        im = alignment_layer_list[j].image_dict[k]
        print_debug ( 50, "    " + str(k) + " alignment points: " + str(im.get_marker_points()) )
      print_debug ( 50, "" )
      print_debug ( 50, "  translation window width = " + str(alignment_layer_list[j].trans_ww) )
      print_debug ( 50, "  translation addx         = " + str(alignment_layer_list[j].trans_addx) )
      print_debug ( 50, "  translation addy         = " + str(alignment_layer_list[j].trans_addy) )
      print_debug ( 50, "" )
      print_debug ( 50, "  affine enabled           = " + str(alignment_layer_list[j].affine_enabled) )
      print_debug ( 50, "  affine window width      = " + str(alignment_layer_list[j].affine_ww) )
      print_debug ( 50, "  affine addx              = " + str(alignment_layer_list[j].affine_addx) )
      print_debug ( 50, "  affine addy              = " + str(alignment_layer_list[j].affine_addy) )
      print_debug ( 50, "" )
      print_debug ( 50, "  bias enabled             = " + str(alignment_layer_list[j].bias_enabled) )
      print_debug ( 50, "  bias dx                  = " + str(alignment_layer_list[j].bias_dx) )
      print_debug ( 50, "  bias dy                  = " + str(alignment_layer_list[j].bias_dy) )


    # Perform the actual alignment
    snr_value = sys.float_info.max
    for apair in align_pairs:
      i = apair[0] # Reference
      j = apair[1] # Current moving
      m = apair[2] # Alignment Method (0=SwimWindow, 1=MatchPoint)
      snr_value = 0


      if alignment_layer_list[j].image_dict == None:
        print_debug ( 50, "Creating image dictionary for layer " + str(j) )
        alignment_layer_list[j].image_dict = {}

      # TEMP dict to try out match point alignment
      if m==1:
        mp_base = alignment_layer_list[j].image_dict['base'].get_marker_points()
        mp_ref = alignment_layer_list[j].image_dict['ref'].get_marker_points()
        layer_dict = {
          "images": {
            "base": {
              "metadata": {
                "match_points": mp_base
              }
            },
            "ref": {
              "metadata": {
                "match_points": mp_ref
              }
            }
          },
          "align_to_ref_method": {
            "selected_method": "Match Point Align",
            "method_options": [
              "Auto Swim Align",
              "Match Point Align"
            ],
            "method_data": {},
            "method_results": {}
          }
        }
      else:
        layer_dict = None

      annotated_img = None
      if i == j:
        # This case (i==j) means make a copy of the original in the destination location
        print_debug ( 20, "\nCopying ( " + alignment_layer_list[i].base_image_name + " to " + os.path.join(scale_dest_path,os.path.basename(alignment_layer_list[i].base_image_name)) + " )" )
        shutil.copyfile ( alignment_layer_list[i].base_image_name, os.path.join(scale_dest_path,os.path.basename(alignment_layer_list[i].base_image_name)) )

        # Create a new identity transform for this layer even though it's not otherwise needed
        alignment_layer_list[j].align_proc = align_swiftir.alignment_process ( alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name,
                                                                               scale_dest_path, layer_dict=layer_dict,
                                                                               x_bias=alignment_layer_list[j].bias_dx, y_bias=alignment_layer_list[j].bias_dy,
                                                                               cumulative_afm=None )

        alignment_layer_list[j].image_dict['ref'] = annotated_image(None, role="ref")
        #alignment_layer_list[j].image_dict['base'] = annotated_image(clone_from=alignment_layer_list[j].base_annotated_image, role="base")
        alignment_layer_list[j].image_dict['aligned'] = annotated_image(clone_from=alignment_layer_list[j].base_annotated_image, role='aligned')

        snr_value = sys.float_info.max

        alignment_layer_list[j].results_dict = {}
        alignment_layer_list[j].results_dict['snr'] = snr_value
        alignment_layer_list[j].results_dict['affine'] = [ [1, 0, 0], [0, 1, 0] ]
        alignment_layer_list[j].results_dict['cumulative_afm'] = [ [1, 0, 0], [0, 1, 0] ]

        alignment_layer_list[j].image_dict['aligned'].clear_non_marker_graphics()
        alignment_layer_list[j].image_dict['aligned'].add_file_name_graphic()

        alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 26, "SNR: inf", coordsys='p', color=[1, .5, .5]) )
        alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 46, "Affine: " + str2D(alignment_layer_list[j].results_dict['affine']), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )
        alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 66, "CumAff: " + str2D(alignment_layer_list[j].results_dict['cumulative_afm']), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )


      else:
        # Align the image at index j with the reference at index i

        if not 'cumulative_afm' in alignment_layer_list[i].results_dict:
          print_debug ( 1, "Cannot align from here (" + str(i) + " to " + str(j) + ") without a previous cumulative affine matrix." )
          return

        prev_afm = [ [ c for c in r ] for r in alignment_layer_list[i].results_dict['cumulative_afm'] ]  # Gets the cumulative from the stored values in previous layer

        print_debug ( 20, "\n" )
        print_debug ( 10, "\nAligning: i=" + str(i) + " to j=" + str(j) )
        print_debug ( 50, "  Calling align_swiftir.align_images( " + alignment_layer_list[i].base_image_name + ", " + alignment_layer_list[j].base_image_name + ", " + scale_dest_path + " )" )

        alignment_layer_list[j].align_proc = align_swiftir.alignment_process ( alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name,
                                                                               scale_dest_path, layer_dict=layer_dict,
                                                                               x_bias=alignment_layer_list[j].bias_dx, y_bias=alignment_layer_list[j].bias_dy,
                                                                               cumulative_afm=prev_afm )
        print_debug ( 70, "\nBefore alignment:\n" )
        print_debug ( 70, str(alignment_layer_list[j].align_proc) )

        # This is the call to alignment_process.align() ...
        #   ... which calls alignment_process.auto_swim_align() ...
        #     ... which builds a recipe and calls recipe.execute() ...
        #       ... which loops through each ingredient and calls ingredient.execute() ...
        #         ... which performs either a Python swim or a C swim ...
        # The actual loading and saving of images is done inside auto_swim_align via:
        #     im_sta = swiftir.loadImage(self.im_sta_fn)
        #     im_mov = swiftir.loadImage(self.im_mov_fn)
        #     swiftir.saveImage(im_aligned,ofn)

        alignment_layer_list[j].align_proc.align()

        print_debug ( 70, "\nAfter alignment:\n" )
        print_debug ( 70, str(alignment_layer_list[j].align_proc) )

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        recipe = alignment_layer_list[j].align_proc.recipe
        new_name = os.path.join ( scale_dest_path, os.path.basename(alignment_layer_list[j].base_image_name) )

        # Put the proper images into the proper window slots

        print_debug ( 60, "Reading in new_name from " + str(new_name) )
        annotated_img = annotated_image(new_name, role='aligned')

        annotated_img.clear_non_marker_graphics()
        annotated_img.add_file_name_graphic()

        annotated_img.graphics_items.append ( graphic_text(2, 26, "SNR: %.4g" % (recipe.ingredients[-1].snr[0]), coordsys='p', color=[1, .5, .5]) )
        annotated_img.graphics_items.append ( graphic_text(2, 46, "Affine: " + str2D(recipe.afm), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )
        annotated_img.graphics_items.append ( graphic_text(2, 66, "CumAff: " + str2D(alignment_layer_list[j].align_proc.cumulative_afm), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )

        alignment_layer_list[j].image_dict['ref'].clear_non_marker_graphics()
        alignment_layer_list[j].image_dict['ref'].add_file_name_graphic()

        alignment_layer_list[j].image_dict['base'].clear_non_marker_graphics()
        alignment_layer_list[j].image_dict['base'].add_file_name_graphic()

        for ri in range(len(recipe.ingredients)):
          # Make a color for this recipe item
          c = [(ri+1)%2,((ri+1)/2)%2,((ri+1)/4)%2]
          r = recipe.ingredients[ri]
          s = len(r.psta[0])
          ww = r.ww
          if type(ww) == type(1):
            # ww is an integer, so turn it into an nxn tuple
            ww = (ww,ww)
          global show_window_centers
          if False or show_window_centers:
            # Draw dots in the center of each psta (could be pmov) with SNR for each
            for wi in range(s):
              try:
                annotated_img.graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
                if not (type(r.snr) is None):
                  annotated_img.graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )

                alignment_layer_list[j].image_dict['ref'].graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
                if not (type(r.snr) is None):
                  alignment_layer_list[j].image_dict['ref'].graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )

                alignment_layer_list[j].image_dict['base'].graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
                if not ( (type(r.snr) is None) or (type(r.snr[wi]) is None) ):
                  alignment_layer_list[j].image_dict['base'].graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )
              except Exception as e:
                print ( "Exception caught while showing window centers: " + str(e) )
                #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
                pass

          print_debug ( 70, "Length of psta = " + str(s) )
          print_debug ( 70, "Length of gitems = " + str(len(annotated_img.graphics_items)) )
          print_debug ( 70, "Length of gi ref = " + str(len(alignment_layer_list[j].image_dict['ref'].graphics_items)) )
          print_debug ( 70, "Length of gi base = " + str(len(alignment_layer_list[j].image_dict['base'].graphics_items)) )

          print_debug ( 50, "  Recipe " + str(ri) + " has " + str(s) + " " + str(ww[0]) + "x" + str(ww[1]) + " windows" )

        alignment_layer_list[j].image_dict['aligned'] = annotated_img
        snr_value = recipe.ingredients[-1].snr[0]

        alignment_layer_list[j].results_dict = {}
        alignment_layer_list[j].results_dict['snr'] = snr_value
        alignment_layer_list[j].results_dict['affine'] = [ [ c for c in r ] for r in recipe.afm ]  # Make a copy
        alignment_layer_list[j].results_dict['cumulative_afm'] = [ [ c for c in r ] for r in alignment_layer_list[j].align_proc.cumulative_afm ]  # Make a copy

      # Check to see if this image should be marked for SNR skipping:
      snr_skip_str = gui_fields.snr_skip.get_text()
      if len(snr_skip_str.strip()) > 0:
        # An snr_skip limit has been entered
        try:
          snr_skip = float(snr_skip_str.strip())
          if snr_value <= snr_skip:
            print_debug ( 20, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
            print_debug ( 20, "SNR of " + str(snr_value) + " is less than SNR Skip of " + str(snr_skip) )
            print_debug ( 20, "  This layer will be marked for skipping in the next pass: " + str(j) )
            print_debug ( 20, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
            alignment_layer_list[j].snr_skip = True
        except:
          print_debug ( 1, "The SNR Skip value should be a number and not " + snr_skip_str )

      # Check to see if the alignment should proceed at all
      snr_halt_str = gui_fields.snr_halt.get_text()
      if len(snr_halt_str.strip()) > 0:
        # An snr_halt limit has been entered
        try:
          snr_halt = float(snr_halt_str.strip())
          if snr_value <= snr_halt:
            print_debug ( 10, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
            print_debug ( 10, "SNR of " + str(snr_value) + " is less than SNR Halt of " + str(snr_halt) )
            print_debug ( 10, "  Alignment stopped on layer " + str(j) )
            print_debug ( 10, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" )
            break
        except:
          print_debug ( 1, "The SNR Halt value should be a number and not " + snr_halt_str )

  else:

    #########################################################
    #########################################################
    ## Call a dynamic external runner
    #########################################################
    #########################################################

    runner_name = str(gui_fields.code_base_select.get_active_text())
    print_debug ( 70, "Dynamic runner: " + runner_name )

    write_json_project ( "run_project.json" )
    module = __import__ ( runner_name[0:-3] )

    # Transfer any global variables into the module
    if 'debug_level' in dir(module):
      module.debug_level = debug_level

    num_forward = None
    num_forward_str = gui_fields.num_align_forward.get_text()
    if len(num_forward_str.strip()) > 0:
      # A forward limit has been entered
      try:
        num_forward = int(num_forward_str.strip())
      except:
        num_forward = None

    snr_skip = None
    snr_skip_str = gui_fields.snr_skip.get_text()
    if len(snr_skip_str.strip()) > 0:
      # An snr_skip limit has been entered
      try:
        snr_skip = float(snr_skip_str.strip())
      except:
        print_debug ( 1, "The SNR Skip value should be a number and not " + snr_skip_str )

    snr_halt = None
    snr_halt_str = gui_fields.snr_halt.get_text()
    if len(snr_halt_str.strip()) > 0:
      # An snr_halt limit has been entered
      try:
        snr_halt = float(snr_halt_str.strip())
      except:
        print_debug ( 1, "The SNR Halt value should be a number and not " + snr_halt_str )

    module.run_alignment ( "run_project.json", # project_file_name,
                           align_all,
                           alignment_layer_index,
                           num_forward,
                           snr_skip,
                           snr_halt )




  # The following work manually, but gave error when done here
  # The try/excepts didn't help
  print_debug ( 50, "Try refreshing" )
  try:
    refresh_all_images()
  except:
    pass
  print_debug ( 50, "Try centering" )
  try:
    center_all_images()
  except:
    pass



def run_callback ( zpa ):
  # print_debug ( 50, "Run " )
  # zpa.user_data['running'] = True
  print_debug ( 50, "Starting a thread" )
  try:
    # thread.start_new_thread ( pyswim.do_alignment, ("data",5,) )
    pass
  except:
    print_debug ( 50, "Unable to start thread" )
  print_debug ( 50, "Done starting a thread" )
  return True

def stop_callback ( zpa ):
  # print_debug ( 50, "Stop " )
  zpa.user_data['running'] = False
  return True

def print_data_structures(panel_list, alignment_layer_list):
  print_debug ( 1, "Data Structures" )
  print_debug ( 1, "=========== " + str(len(panel_list)) + " Panels ===========" )
  pn = 0
  for panel in panel_list:
    print_debug ( 1, " Panel List [" + str(pn) + "].role = " + str(panel.role) )
    pn += 1

  ln = 0
  print_debug ( 1, "=========== " + str(len(alignment_layer_list)) + " Alignment Layers ===========" )
  for layer in alignment_layer_list:
    print_debug ( 1, " Layer " + str(ln) + " has " + str(len(layer.image_dict.keys()) ) + str(" images") )
    for k in sorted(layer.image_dict.keys(),reverse=True):
      im = layer.image_dict[k]
      print_debug ( 1, "   " + k + " image: " + str(im).split()[-1][0:-1] ) # key image: hex address
      print_debug ( 1, "     file: " + str(im.file_name).split('/')[-1] )
      print_debug ( 1, "     markers: " + str([[round(v*10)/10 for v in p] for p in im.get_marker_points()]) )
    ln += 1
  # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

def upgrade_proj_dict ( proj_dict ):
  if not ('version' in proj_dict):
    print_debug ( 0, "Unable to read from files with no version number ... update code to handle this format." )
    exit (99)
  if proj_dict['version'] < 0.099:
    print_debug ( 0, "Unable to read from versions before 0.1 ... update code to handle this format." )
    exit (99)
  if proj_dict['version'] < 0.199:
    # This is pre 0.2, so add the "scales" key with a single scale of 1
    # The previous alignment stack will now reside below key "1"
    warn_dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK, message_format="Upgrading model from " + str(proj_dict['version']) + " to 0.2\nSaving will use the new format." )
    response = warn_dialog.run()
    warn_dialog.destroy()

    # Create the new structure
    proj_dict['data']['scales'] = {}
    proj_dict['data']['scales']['1'] = {}
    # Transfer the "alignment_stack" list from the "data" dictionary to the "data/scales/1" dictionary
    proj_dict['data']['scales']['1']['alignment_stack'] = proj_dict['data'].pop('alignment_stack')
    # Upgrade the version number
    proj_dict['version'] = 0.2
  if proj_dict['version'] > 0.201:
    # This program is not written for newer versions
    print_debug ( 0, "Unable to read from versions above 0.2 ... update code to handle this format." )
    exit (99)
  return proj_dict

def load_from_proj_dict ( proj_dict ):

  global project_path
  global project_file_name
  global destination_path
  global zpa_original
  global alignment_layer_list
  global alignment_layer_index
  global panel_list

  global point_cursor
  global cursor_options
  global point_mode
  global point_delete_mode

  global gui_fields
  global scales_dict

  proj_dict = upgrade_proj_dict ( proj_dict )

  if 'plot_code' in proj_dict:
    code_l = proj_dict['plot_code']
    code_e = ''.join(code_l)
    code_p = base64.b64decode ( code_e )
    code_c = pickle.loads ( code_p )
    global current_plot_code
    current_plot_code = code_c

  if 'user_settings' in proj_dict:
    if 'max_image_file_size' in proj_dict['user_settings']:
      global max_image_file_size
      max_image_file_size = proj_dict['user_settings']['max_image_file_size']

  if 'data' in proj_dict:
    if 'destination_path' in proj_dict['data']:
      destination_path = proj_dict['data']['destination_path']
      print ( "load_from_proj_dict found destination_path = " + destination_path )
      print ( "load_from_proj_dict found project_path = " + str(project_path) )
      # Make the destination absolute
      if not os.path.isabs(destination_path):
        destination_path = os.path.join ( project_path, destination_path )
      destination_path = os.path.realpath ( destination_path )

      global gtk_mode
      if gtk_mode:
        gui_fields.dest_label.set_text ( "Destination: " + str(destination_path) )
      else:
        gui_fields.proj_label.setText ( "Destination: " + str(destination_path) )

    current_scale = 1
    if 'current_scale' in proj_dict['data']:
      current_scale = proj_dict['data']['current_scale']

    if 'scales' in proj_dict['data']:

      gui_fields.scales_list = sorted ( [ int(k) for k in proj_dict['data']['scales'].keys() ] )
      sd = proj_dict['data']['scales']

      scales_dict = {}
      panel_names_list = []

      for scale_key in gui_fields.scales_list:
        if 'alignment_stack' in sd[str(scale_key)]:
          imagestack = sd[str(scale_key)]['alignment_stack']
          if len(imagestack) > 0:
            alignment_layer_index = 0
            alignment_layer_list = []

            sd[current_scale] = alignment_layer_list
            for json_alignment_layer in imagestack:
              if 'images' in json_alignment_layer:
                im_list = json_alignment_layer['images']
                # Add any needed panels for this scale and layer
                for k in im_list.keys():
                  if not (k in panel_names_list):
                    panel_names_list.append ( k )

                if 'base' in im_list:
                  base = im_list['base']
                  if 'filename' in base:
                    image_fname = base['filename']
                    # Convert to absolute as needed
                    if not os.path.isabs(image_fname):
                      image_fname = os.path.join ( project_path, image_fname )
                    image_fname = os.path.realpath ( image_fname )
                    a = alignment_layer ( image_fname )  # This will put the image into the "base" role
                    if 'skip' in json_alignment_layer:
                      a.skip = json_alignment_layer['skip']

                    if 'align_to_ref_method' in json_alignment_layer:
                      json_align_to_ref_method = json_alignment_layer['align_to_ref_method']
                      a.align_method_text = str(json_align_to_ref_method['selected_method'])
                      opts = [ str(x) for x in json_align_to_ref_method['method_options'] ]
                      a.align_method = opts.index(a.align_method_text)

                      if 'method_data' in json_align_to_ref_method:
                        pars = json_align_to_ref_method['method_data']
                        a.trans_ww = pars['window_size']
                        a.trans_addx = pars['addx']
                        a.trans_addy = pars['addy']
                        a.affine_enabled = True
                        a.affine_ww = pars['window_size']
                        a.affine_addx = pars['addx']
                        a.affine_addy = pars['addy']
                        a.bias_enabled = False
                        a.bias_dx = 0
                        a.bias_dy = 0
                        print_debug ( 70, "Got method_data" + str(pars) )
                        if 'alignment_option' in pars:
                          a.init_refine_apply = pars['alignment_option']
                          print_debug ( 70, "  ... found alignment_option:" + str(a.init_refine_apply) )
                        if 'bias_x_per_image' in pars:
                          a.bias_dx = pars['bias_x_per_image']
                          print_debug ( 70, "  ... found bias_x_per_image:" + str(a.bias_dx) )
                        if 'bias_y_per_image' in pars:
                          a.bias_dy = pars['bias_y_per_image']
                          print_debug ( 70, "  ... found bias_y_per_image:" + str(a.bias_dy) )
                        if 'bias_scale_x_per_image' in pars:
                          a.bias_scale_x = pars['bias_scale_x_per_image']
                          print_debug ( 70, "  ... found bias_scale_x_per_image:" + str(a.bias_scale_x) )
                        if 'bias_scale_y_per_image' in pars:
                          a.bias_scale_y = pars['bias_scale_y_per_image']
                          print_debug ( 70, "  ... found bias_scale_y_per_image:" + str(a.bias_scale_y) )
                        if 'bias_skew_x_per_image' in pars:
                          a.bias_skew_x = pars['bias_skew_x_per_image']
                          print_debug ( 70, "  ... found bias_skew_x_per_image:" + str(a.bias_skew_x) )
                        if 'bias_rot_per_image' in pars:
                          a.bias_rotation = pars['bias_rot_per_image']
                          print_debug ( 70, "  ... found bias_rot_per_image:" + str(a.bias_rotation) )

                      if 'method_results' in json_align_to_ref_method:
                        json_method_results = json_align_to_ref_method['method_results']
                        if 'cumulative_afm' in json_method_results:
                          print_debug ( 60, "Loading a cumulative_afm from JSON" )

                          a.results_dict['snr'] = json_method_results['snr'] # Copy
                          a.results_dict['affine'] = [ [ c for c in r ] for r in json_method_results['affine_matrix'] ] # Copy
                          a.results_dict['cumulative_afm'] = [ [ c for c in r ] for r in json_method_results['cumulative_afm'] ] # Copy

                    # Load match points into the base image (if found)
                    if 'metadata' in base:
                      if 'match_points' in base['metadata']:
                        mp = base['metadata']['match_points']
                        for p in mp:
                          print_debug ( 80, "%%%% GOT BASE MATCH POINT: " + str(p) )
                          m = graphic_marker ( p[0], p[1], 6, 'i', [1, 1, 0.5] )
                          a.image_dict['base'].graphics_items.append ( m )
                      if 'annotations' in base['metadata']:
                        ann_list = base['metadata']['annotations']
                        for ann_item in ann_list:
                          print_debug ( 60, "Base has " + str(ann_item) )
                          a.image_dict['base'].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )

                    # Only look for a ref or aligned if there has been a base
                    if 'ref' in im_list:
                      ref = im_list['ref']
                      if 'filename' in ref:
                        image_fname = ref['filename']
                        if len(image_fname) <= 0:
                          # Don't try to load empty images
                          a.image_dict['ref'] = annotated_image(None, role="ref")
                        else:
                          # Convert to absolute as needed
                          if not os.path.isabs(image_fname):
                            image_fname = os.path.join ( project_path, image_fname )
                          image_fname = os.path.realpath ( image_fname )
                          a.image_dict['ref'] = annotated_image(image_fname,role="ref")

                          # Load match points into the ref image (if found)
                          if 'metadata' in ref:
                            if 'match_points' in ref['metadata']:
                              mp = ref['metadata']['match_points']
                              for p in mp:
                                print_debug ( 80, "%%%% GOT REF MATCH POINT: " + str(p) )
                                m = graphic_marker ( p[0], p[1], 6, 'i', [1, 1, 0.5] )
                                a.image_dict['ref'].graphics_items.append ( m )
                            if 'annotations' in ref['metadata']:
                              ann_list = ref['metadata']['annotations']
                              for ann_item in ann_list:
                                print_debug ( 60, "Ref has " + str(ann_item) )
                                a.image_dict['ref'].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )

                    if 'aligned' in im_list:
                      aligned = im_list['aligned']
                      if 'filename' in aligned:
                        image_fname = aligned['filename']
                        if len(image_fname) <= 0:
                          # Don't try to load empty images
                          a.image_dict['ref'] = annotated_image(None, role="ref")
                        else:
                          # Convert to absolute as needed
                          if not os.path.isabs(image_fname):
                            image_fname = os.path.join ( project_path, image_fname )
                          image_fname = os.path.realpath ( image_fname )
                          a.image_dict['aligned'] = annotated_image(image_fname,role='aligned')
                      if 'metadata' in aligned:
                        if 'annotations' in aligned['metadata']:
                          ann_list = aligned['metadata']['annotations']
                          for ann_item in ann_list:
                            print_debug ( 60, "Aligned has " + str(ann_item) )
                            a.image_dict['aligned'].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )

                    alignment_layer_list.append ( a )
                    print_debug ( 70, "Internal bias_x after appending: " + str(a.bias_dx) )

            scales_dict[scale_key] = alignment_layer_list


      print_debug ( 70, "Final panel_names_list: " + str(panel_names_list) )

      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      setup_initial_panels()

      # TODO Add other panels as needed


      update_menu_scales_from_gui_fields()

      alignment_layer_list = scales_dict[gui_fields.scales_list[0]]

      # Because changing the scale will save values from fields into this layer ...
      # We need to put these newly loaded layer values into the fields first:
      store_current_layer_into_fields()

      set_selected_scale_to ( current_scale )

    if 'current_layer' in proj_dict['data']:
      alignment_layer_index = proj_dict['data']['current_layer']

      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


def update_newly_loaded_proj():

  global project_path
  global project_file_name
  global destination_path
  global zpa_original
  global alignment_layer_list
  global alignment_layer_index
  global panel_list

  global point_cursor
  global cursor_options
  global point_mode
  global point_delete_mode

  # Fill the GUI fields from the current state
  store_current_layer_into_fields()
  # Copy the "base" images into the "ref" images for the next layer
  # This is SWiFT specific, but makes it simpler to use for now
  layer_index = 0
  for a in alignment_layer_list:
    if layer_index > 0:
      # Create a reference image from the previous layer if it wasn't read in via the JSON above
      if not 'ref' in a.image_dict:
        a.image_dict['ref'] = annotated_image(clone_from=alignment_layer_list[layer_index-1].image_dict['base'],role="ref")
    # Create an empty aligned image as a place holder (to keep the panels from changing after alignment)
    #a.image_dict['aligned'] = annotated_image(None,role='aligned')
    layer_index += 1
  refresh_all_images()
  center_all_images()
  panel_index = 0
  for panel in panel_list:
    if panel_index == 0:
      panel.role = 'ref'
      panel.point_add_enabled = True
    elif panel_index == 1:
      panel.role = 'base'
      panel.point_add_enabled = True
    elif panel_index == 2:
      panel.role = 'aligned'
      panel.point_add_enabled = False
    panel.force_center = True
    panel.queue_draw()
    panel_index += 1
  zpa_original.force_center = True
  zpa_original.queue_draw()

def update_menu_scales_from_gui_fields():

  global zpa_original
  global scales_dict
  global current_scale
  global gui_fields

  if len(gui_fields.scales_list) <= 0:
    current_scale = 1
  else:
    if not (current_scale in gui_fields.scales_list):
      current_scale = gui_fields.scales_list[0]
  # print_debug ( 70, str(gui_fields.scales_list) )
  # Update the menu items in the "Scales" menu
  # Note that this gets behind the scenes of the "app_window" API
  # Some of this could be added to the "app_window" API at some point
  global menu_bar
  scales_menu = None
  for m in menu_bar.get_children():
    label = m.get_children()[0].get_label()
    # print_debug ( 70, label )
    if label == '_Scales':
      scales_menu = m.get_submenu()
  if scales_menu != None:
    # Remove all the old items and recreate them from the current list
    while len(scales_menu) > 0:
      scales_menu.remove ( scales_menu.get_children()[0] )
    for s in gui_fields.scales_list:
      item = gtk.CheckMenuItem(label="Scale "+str(s))
      item.set_active ( s == current_scale )
      item.connect ( 'activate', menu_callback, ("SelectScale_"+str(s), zpa_original) )
      scales_menu.append ( item )
      item.show()

  # Add the scales to the menu
  for s in gui_fields.scales_list:
    if not s in scales_dict:
      scales_dict[s] = []


def set_selected_scale_to ( requested_scale ):

  global scales_dict
  global current_scale
  global alignment_layer_list
  global zpa_original
  global panel_list

  if requested_scale in scales_dict:

    # Store the alignment_layer parameters into the image layer being exited
    store_fields_into_current_layer()

    print_debug ( 40, "Changing to scale " + str(requested_scale) )
    # Save the current alignment_layer_list into the current_scale
    scales_dict[current_scale] = alignment_layer_list
    # Change the current scale
    current_scale = requested_scale
    # Make the new scale active
    alignment_layer_list = scales_dict[current_scale]
    zpa_original.queue_draw()
    for p in panel_list:
      p.queue_draw()

    global menu_bar
    scales_menu = None
    for m in menu_bar.get_children():
      label = m.get_children()[0].get_label()
      print_debug ( 70, label )
      if label == '_Scales':
        scales_menu = m.get_submenu()
    if scales_menu != None:
      # Remove all the old items and recreate them from the current list
      while len(scales_menu) > 0:
        scales_menu.remove ( scales_menu.get_children()[0] )
      for s in gui_fields.scales_list:
        item = gtk.CheckMenuItem(label="Scale "+str(s))
        item.set_active ( s == current_scale )
        item.connect ( 'activate', menu_callback, ("SelectScale_"+str(s), zpa_original) )
        scales_menu.append ( item )
        item.show()

    # Display the alignment_layer parameters from the new section being viewed
    store_current_layer_into_fields()

  else:
    print_debug ( 70, "Scale " + str(requested_scale) + " is not in " + str(scales_dict.keys()) )



code_dialog = None
code_store = None
code_entry = None

def menu_callback ( widget, data=None ):
  # Menu items will trigger this call
  # The menu items are set up to pass either a tuple:
  #  (command_string, zpa)
  # or a plain string:
  #  command_string
  # Checking the type() of data will determine which
  global debug_level

  if type(data) == type((True,False)):
    # Any tuple passed is assumed to be: (command, zpa)
    command = data[0]
    zpa = data[1]

    global project_path
    global project_file_name
    global destination_path
    global zpa_original
    global scales_dict
    global current_scale
    global alignment_layer_list
    global alignment_layer_index
    global panel_list
    global import_tiled

    global point_cursor
    global cursor_options
    global point_mode
    global point_delete_mode

    global code_dialog
    global code_store
    global code_entry
    global current_plot_code

    global generate_as_tiled

    if command == "Fast":

      zpa.user_data['frame_delay'] = 0.01

    elif command == "Med":

      zpa.user_data['frame_delay'] = 0.1

    elif command == "Slow":

      zpa.user_data['frame_delay'] = 1.0

    elif command == "ToggleLegend":

      zpa.user_data['show_legend'] = not zpa.user_data['show_legend']
      zpa.queue_draw()

    elif command == "Affine":

      for i in range(len(alignment_layer_list)):

        if type(alignment_layer_list[i]) == type(None):
          print_debug ( 5, "  Layer " + str(i) + ": Alignment is None" )
        else:
          if type(alignment_layer_list[i].align_proc) == type(None):
            print_debug ( 5, "  Layer " + str(i) + ": Alignment Process is None" )
          else:
            affine = alignment_layer_list[i].align_proc.cumulative_afm
            print_debug ( 50, "  Layer " + str(i) + ": Affine is " + str(affine) )

    elif command == "Debug":

      print_debug ( -1, "Handy global items:" )
      print_debug ( -1, "  project_path" )
      print_debug ( -1, "  project_file_name" )
      print_debug ( -1, "  destination_path" )
      print_debug ( -1, "  zpa_original" )
      print_debug ( -1, "  alignment_layer_list" )
      print_debug ( -1, "  alignment_layer_index" )
      print_debug ( -1, "  show_window_centers" )
      print_debug ( -1, "  point_mode" )
      print_debug ( -1, "Handy local items:" )
      print_debug ( -1, "  widget" )
      print_debug ( -1, "  data" )
      print_debug ( -1, "  command" )
      print_debug ( -1, "  zpa" )

      __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      zpa.queue_draw()

    elif command == "SetDest":

      file_chooser = gtk.FileChooserDialog(title="Select Destination Directory", action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
	                                         buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
      file_chooser.set_select_multiple(False)
      file_chooser.set_default_response(gtk.RESPONSE_OK)
      response = file_chooser.run()
      if response == gtk.RESPONSE_OK:
        destination_path = file_chooser.get_filename()
        # Ensure that it's actually a directory and not a file:
        if not os.path.isdir(destination_path):
          destination_path = os.path.dirname(destination_path)
        destination_path = os.path.realpath(destination_path)
        print_debug ( 50, "Selected Directory: " + str(destination_path) )

        gui_fields.dest_label.set_text ( "Destination: " + str(destination_path) )

      file_chooser.destroy()
      print_debug ( 90, "Done with dialog" )
      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      zpa.queue_draw()

    elif command == "ImImport":

      file_chooser = gtk.FileChooserDialog(title="Select Images", action=gtk.FILE_CHOOSER_ACTION_OPEN,
	                                         buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
      file_chooser.set_select_multiple(True)
      file_chooser.set_default_response(gtk.RESPONSE_OK)
      #file_chooser.show()

      image_filter=gtk.FileFilter()
      image_filter.set_name("Images")
      image_filter.add_pattern("*.[Jj][Pp][Gg]")
      image_filter.add_pattern("*.[Jj][Pp][Ee][Gg]")
      image_filter.add_pattern("*.[Pp][Nn][Gg]")
      image_filter.add_pattern("*.[Tt][Ii][Ff]")
      image_filter.add_pattern("*.[Tt][Ii][Ff][Ff]")
      image_filter.add_pattern("*.[Tt][Tt][Ii][Ff]")
      image_filter.add_pattern("*.[Gg][Ii][Ff]")
      file_chooser.add_filter(image_filter)
      image_filter=gtk.FileFilter()
      image_filter.set_name("All Files")
      image_filter.add_pattern("*")
      file_chooser.add_filter(image_filter)
      response = file_chooser.run()

      if response == gtk.RESPONSE_OK:
        file_name_list = file_chooser.get_filenames()
        print_debug ( 20, "Selected Files: " + str(file_name_list) )
        # alignment_layer_list = []
        # scales_dict[current_scale] = alignment_layer_list
        for f in file_name_list:
          a = alignment_layer ( f )
          alignment_layer_list.append ( a )

      file_chooser.destroy()
      print_debug ( 90, "Done with dialog" )
      # Draw the panels ("windows")
      for panel in panel_list:
        panel.role = 'base'
        panel.force_center = True
        panel.queue_draw()
      zpa_original.force_center = True
      zpa_original.queue_draw()

      ##### Begin Pasted from OpenProj
      print_debug ( 90, "Done with dialog" )
      # Copy the "base" images into the "ref" images for the next layer
      # This is SWiFT specific, but makes it simpler to use for now
      layer_index = 0
      for a in alignment_layer_list:
        if layer_index > 0:
          # Create a reference image from the previous layer if it wasn't read in via the JSON above
          if not 'ref' in a.image_dict:
            a.image_dict['ref'] = annotated_image(clone_from=alignment_layer_list[layer_index-1].image_dict['base'],role="ref")
        # Create an empty aligned image as a place holder (to keep the panels from changing after alignment)
        #a.image_dict['aligned'] = annotated_image(None,role='aligned')
        layer_index += 1

      setup_initial_panels()

      refresh_all_images()
      center_all_images()
      panel_index = 0
      for panel in panel_list:
        if panel_index == 0:
          panel.role = 'ref'
          panel.point_add_enabled = True
        elif panel_index == 1:
          panel.role = 'base'
          panel.point_add_enabled = True
        elif panel_index == 2:
          panel.role = 'aligned'
          panel.point_add_enabled = False
        panel.force_center = True
        panel.queue_draw()
        panel_index += 1
      zpa_original.force_center = True
      zpa_original.queue_draw()
      ##### End Pasted from OpenProj



    elif command == "OpenProj":

      file_chooser = gtk.FileChooserDialog(title="Open Project", action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                           buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
      file_chooser.set_select_multiple(False)
      file_chooser.set_default_response(gtk.RESPONSE_OK)

      image_filter=gtk.FileFilter()
      image_filter.set_name("JSON")
      image_filter.add_pattern("*.json")
      file_chooser.add_filter(image_filter)
      image_filter=gtk.FileFilter()
      image_filter.set_name("All Files")
      image_filter.add_pattern("*")
      file_chooser.add_filter(image_filter)
      response = file_chooser.run()

      if response == gtk.RESPONSE_OK:
        open_name = file_chooser.get_filename()
        if open_name != None:
          open_name = os.path.realpath(open_name)
          if not os.path.isdir(open_name):
            # It's a real file
            project_file_name = open_name
            project_path = os.path.dirname(project_file_name)

            gui_fields.proj_label.set_text ( "Project File: " + str(project_file_name) )

            f = open ( project_file_name, 'r' )
            text = f.read()
            f.close()

            proj_dict = json.loads ( text )
            print_debug ( 70, str(proj_dict) )
            print_debug ( 5, "Project file version " + str(proj_dict['version']) )

            load_from_proj_dict ( proj_dict )

            '''
            # Test to explore how the JSONEncoder works for indenting JSON output
            # This works reasonably well, but short arrays and dictionaries are not in-line
            # Also note that this must be done BEFORE calling load_from_proj_dict
            # This is because load_from_proj_dict appears to add non-JSON compatible objects
            '''

            ''' In later tests this gives an error ... so comment out

              Saving JSON to "test_json_output.json"
              Traceback (most recent call last):
                File "pyswift_gui.py", line 2547, in menu_callback
                  proj_encoded_dict = jdencode.encode ( proj_dict )
                File "/usr/lib/python2.7/json/encoder.py", line 209, in encode
                  chunks = list(chunks)
                File "/usr/lib/python2.7/json/encoder.py", line 434, in _iterencode
                  for chunk in _iterencode_dict(o, _current_indent_level):
                File "/usr/lib/python2.7/json/encoder.py", line 408, in _iterencode_dict
                  for chunk in chunks:
                File "/usr/lib/python2.7/json/encoder.py", line 408, in _iterencode_dict
                  for chunk in chunks:
                File "/usr/lib/python2.7/json/encoder.py", line 408, in _iterencode_dict
                  for chunk in chunks:
                File "/usr/lib/python2.7/json/encoder.py", line 332, in _iterencode_list
                  for chunk in chunks:
                File "/usr/lib/python2.7/json/encoder.py", line 442, in _iterencode
                  o = _default(o)
                File "/usr/lib/python2.7/json/encoder.py", line 184, in default
                  raise TypeError(repr(o) + " is not JSON serializable")
              TypeError: <__main__.alignment_layer instance at 0x7f9fe9a89a28> is not JSON serializable

            print_debug ( 0, "Saving JSON to \"test_json_output.json\"" )
            jdencode = json.JSONEncoder ( indent=2, separators=(",", ": ") )
            if False:
              proj_encoded_dict = jdencode.iterencode ( proj_dict )
              f = open ( "test_json_output.json", 'w' )
              for chunk in proj_encoded_dict:
                f.write ( chunk )
              f.close()
            else:
              proj_encoded_dict = jdencode.encode ( proj_dict )
              f = open ( "test_json_output.json", 'w' )
              f.write ( proj_encoded_dict )
              f.close()
            '''



      file_chooser.destroy()
      print_debug ( 90, "Done with dialog" )

      update_newly_loaded_proj()



    elif (command == "SaveProj") or (command == "SaveProjAs"):

      print_debug ( 50, "Save with: project_path = " + str(project_path) )
      print_debug ( 50, "Save with: project_file_name = " + str(project_file_name) )
      if (len(project_file_name) <= 0) or (command == "SaveProjAs"):
        # Prompt for a file name

        file_chooser = gtk.FileChooserDialog(title="Save Project", action=gtk.FILE_CHOOSER_ACTION_SAVE,
	                                           buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        file_chooser.set_select_multiple(False)
        file_chooser.set_default_response(gtk.RESPONSE_OK)
        #file_chooser.show()

        image_filter=gtk.FileFilter()
        image_filter.set_name("JSON")
        image_filter.add_pattern("*.json")
        file_chooser.add_filter(image_filter)
        image_filter=gtk.FileFilter()
        image_filter.set_name("All Files")
        image_filter.add_pattern("*")
        file_chooser.add_filter(image_filter)
        response = file_chooser.run()

        if response == gtk.RESPONSE_OK:
          save_name = file_chooser.get_filename()
          if save_name != None:

            save_name = os.path.realpath(save_name)
            if not os.path.isdir(save_name):
              # It's a real file
              project_file_name = save_name
              project_path = os.path.dirname(project_file_name)

        file_chooser.destroy()
        print_debug ( 90, "Done with dialog" )

      if len(project_file_name) > 0:

        # Call the project writing function

        write_json_project ( project_file_name )

    elif command == "MaxFileSize":

      global max_image_file_size
      label = gtk.Label("Enter max image file size:")
      dialog = gtk.Dialog("Set Max Image File Size",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      max_entry = gtk.Entry(20)
      max_entry.set_text ( str ( max_image_file_size ) )

      #checkbox = gtk.CheckButton("Useless checkbox")
      #dialog.vbox.pack_end(checkbox)
      dialog.vbox.pack_end(max_entry)
      #dialog.action_area.pack_end(checkbox)
      #checkbox.show()
      max_entry.show()
      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        print_debug ( 70, str(max_entry.get_text()) )
        #print_debug ( 50, str ( [ int(t) for t in str(scales_entry.get_text()).split(' ') ] ) )
        try:
          max_image_file_size = int(str(max_entry.get_text()))
          print_debug ( 70, "Max file size set to " + str(max_image_file_size) )
        except:
          print_debug ( 70, "Unable to parse " + str(max_entry.get_text()) + " into an integer" )
      dialog.destroy()

    elif command == "DefScales":

      label = gtk.Label("Enter list of scales:")
      dialog = gtk.Dialog("Define Scales",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      scales_entry = gtk.Entry(20)
      scales_entry.set_text ( str ( ' '.join ( [ str(n) for n in gui_fields.scales_list ] ) ) )
      dialog.vbox.pack_end(scales_entry)
      scales_entry.show()

      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        # print_debug ( 70, str(scales_entry.get_text()) )
        gui_fields.scales_list = [ t for t in str(scales_entry.get_text()).split(' ') ]
        gui_fields.scales_list = [ int(t) for t in gui_fields.scales_list if len(t) > 0 ]

        update_menu_scales_from_gui_fields()

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      dialog.destroy()

    elif command.startswith ('SelectScale_'):
      cur_scale = -1
      try:
        cur_scale = int(command[len('SelectScale_'):])
      except:
        cur_scale = -1
      set_selected_scale_to ( cur_scale )
      print_debug ( 40, "Centering images when changing scales" )
      center_all_images()


    elif command == "GenAsTiled":
      generate_as_tiled = not generate_as_tiled
      print_debug ( 40, "Generate as tiled = " + str(generate_as_tiled) )

    elif command == "ImportTiled":
      import_tiled = not import_tiled
      print_debug ( 40, "Import tiled = " + str(import_tiled) )

    elif command == "ShowTiled":
      global show_tiled
      show_tiled = not show_tiled
      print_debug ( 40, "Show tiled = " + str(show_tiled) )
      zpa_original.queue_draw()


    elif command == "GenAllScales":
      print_debug ( 40, "Create images at all scales: " + str ( gui_fields.scales_list ) )

      if len(destination_path) <= 0:
        check_dest = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="No Destination Set")
        response = check_dest.run()
        check_dest.destroy()
      else:
        for scale in gui_fields.scales_list:
          print_debug ( 70, "Creating images for scale " + str(scale) )

          subdir = 'scale_' + str(scale)
          subdir_path = os.path.join(destination_path,subdir)
          print_debug ( 70, "Creating a subdirectory named " + subdir_path )
          try:
            os.mkdir ( subdir_path )
          except:
            # This catches directories that already exist
            pass
          src_path = os.path.join(subdir_path,'img_src')
          print_debug ( 70, "Creating source subsubdirectory named " + src_path )
          try:
            os.mkdir ( src_path )
          except:
            # This catches directories that already exist
            pass
          aligned_path = os.path.join(subdir_path,'img_aligned')
          print_debug ( 70, "Creating aligned subsubdirectory named " + aligned_path )
          try:
            os.mkdir ( aligned_path )
          except:
            # This catches directories that already exist
            pass

          for al in alignment_layer_list:
            try:
              #original_name = os.path.join(destination_path,os.path.basename(al.base_image_name))
              original_name = al.base_image_name
              new_name = os.path.join(src_path,os.path.basename(original_name))
              if generate_as_tiled:
                # Generate as tiled images (means duplicating the originals also)
                tiled_name = os.path.splitext(new_name)[0] + ".ttif"
                print_debug ( 70, "Resizing " + original_name + " to " + tiled_name )
                if False:
                  # Generate internally
                  # Don't know how to do this and make tiles yet
                  img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage ( original_name ), fac=scale )
                  align_swiftir.swiftir.saveImage ( img, new_name )
                else:
                  # Scale as before:
                  img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage ( original_name ), fac=scale )
                  align_swiftir.swiftir.saveImage ( img, new_name )
                  # Use "convert" from ImageMagick to hopefully tile in place
                  import subprocess
                  p = subprocess.Popen ( ['/usr/bin/convert', '-version'] )
                  p = subprocess.Popen ( ['/usr/bin/convert', new_name, "-compress", "None", "-define", "tiff:tile-geometry=1024x1024", "tif:"+tiled_name] )
                  p.wait() # Allow the subprocess to complete before deleting the input file!!
                  os.remove ( new_name ) # This would be the file name of the resized copy of the original image
              else:
                # Generate non-tiled images
                if scale == 1:
                  if os.name == 'posix':
                    print_debug ( 70, "Posix: Linking " + original_name + " to " + new_name )
                    os.symlink ( original_name, new_name )
                  else:
                    print_debug ( 70, "Non-Posix: Copying " + original_name + " to " + new_name )
                    shutil.copyfile ( original_name, new_name )
                else:
                  print_debug ( 70, "Resizing " + original_name + " to " + new_name )
                  img = align_swiftir.swiftir.scaleImage ( align_swiftir.swiftir.loadImage ( original_name ), fac=scale )
                  align_swiftir.swiftir.saveImage ( img, new_name )
            except:
              print_debug ( 10, "Error: Failed to copy?" )
              pass


    elif command == "GenMissingScales":
      print_debug ( 20, "Create images at missing scales in: " + str ( gui_fields.scales_list ) )

    elif command == "ImportAllScales":
      print_debug ( 20, "Import images at all scales in: " + str ( gui_fields.scales_list ) )

      if len(destination_path) <= 0:
        check_dest = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="No Destination Set")
        response = check_dest.run()
        check_dest.destroy()
      else:

        print_debug ( 20, "Clearing all layers..." )
        alignment_layer_index = 0
        alignment_layer_list = []
        scales_dict[current_scale] = alignment_layer_list
        zpa_original.queue_draw()
        for p in panel_list:
          p.queue_draw()

        for scale in gui_fields.scales_list:
          print_debug ( 70, "Importing images for scale " + str(scale) )
          scales_dict[scale] = []
          if True or (scale != 1):
            subdir = 'scale_' + str(scale)
            subdir_path = os.path.join(destination_path,subdir,'img_src')
            print_debug ( 70, "Importing from a subdirectory named " + subdir_path )
            file_list = os.listdir ( subdir_path )
            file_list = [ f for f in file_list if '.' in f ]  # Select only those that have a "." in the file name
            file_list = [ f for f in file_list if f[f.rfind('.'):].lower() in ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.ttif', '.gif' ] ] # Be sure that they have a "." in the file name
            print_debug ( 70, "Presorted File List:\n" + str(file_list) )
            file_list = sorted(file_list)
            print_debug ( 70, "Sorted File List:\n" + str(file_list) )
            for f in file_list:
              print_debug ( 70, " Found image file " + f )
              a = alignment_layer ( os.path.join ( subdir_path, f ) )
              scales_dict[scale].append ( a )

            ##### Begin Pasted from OpenProj
            # Copy the "base" images into the "ref" images for the next layer
            # This is SWiFT specific, but makes it simpler to use for now
            layer_index = 0
            for a in scales_dict[scale]:
              if layer_index > 0:
                # Create a reference image from the previous layer if it wasn't read in via the JSON above
                if not 'ref' in a.image_dict:
                  a.image_dict['ref'] = annotated_image(clone_from=scales_dict[scale][layer_index-1].image_dict['base'],role="ref")
              # Create an empty aligned image as a place holder (to keep the panels from changing after alignment)
              #a.image_dict['aligned'] = annotated_image(None,role='aligned')
              layer_index += 1

        alignment_layer_list = scales_dict[gui_fields.scales_list[0]]

        # Draw the panels ("windows")
        for panel in panel_list:
          panel.role = 'base'
          panel.force_center = True
          panel.queue_draw()
        zpa_original.force_center = True
        zpa_original.queue_draw()

        refresh_all_images()
        center_all_images()
        panel_index = 0
        for panel in panel_list:
          if panel_index == 0:
            panel.role = 'ref'
            panel.point_add_enabled = True
          elif panel_index == 1:
            panel.role = 'base'
            panel.point_add_enabled = True
          elif panel_index == 2:
            panel.role = 'aligned'
            panel.point_add_enabled = False
          panel.force_center = True
          panel.queue_draw()
          panel_index += 1
        zpa_original.force_center = True
        zpa_original.queue_draw()
        ##### End Pasted from OpenProj
        ##### End Pasted from ImImport


    elif command == "DelAllScales":

      label = gtk.Label("Delete images for all scales:")
      dialog = gtk.Dialog("Delete Scaled Images",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      scales_to_delete = [ "scale_" + str(n) for n in gui_fields.scales_list if n != 1 ]
      delete_string = gtk.Label ( "Delete: " + str(' '.join ( scales_to_delete ) ) )
      dialog.vbox.pack_end(delete_string)
      delete_string.show()

      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        # print_debug ( 70, str(scales_entry.get_text()) )
        for f in scales_to_delete:
          print_debug ( 70, "Deleting all files in " + f )

        gui_fields.scales_list = [ 1 ]

        update_menu_scales_from_gui_fields()

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      dialog.destroy()


    elif command == "DelMissingScales":
      print_debug ( 70, "Prune missing scales from: " + str ( gui_fields.scales_list ) )

    elif command == "ClearLayers":

      clear_all = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="Remove All Layers?")
      response = clear_all.run()
      if response == gtk.RESPONSE_OK:
        print_debug ( 20, "Clearing all layers..." )
        scales_dict = {}
        alignment_layer_index = 0
        alignment_layer_list = []
        current_scale = 1
        scales_dict[current_scale] = alignment_layer_list
      zpa_original.queue_draw()
      for p in panel_list:
        p.queue_draw()
      clear_all.destroy()

    elif command == "ClearEverything":

      clear_all = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="Remove Everything?")
      response = clear_all.run()
      if response == gtk.RESPONSE_OK:
        print_debug ( 20, "Clearing all layers..." )

        for scale in scales_dict.keys():
          print_debug ( 70, "Deleting images for scale " + str(scale) )
          if True or (scale != 1):
            subdir = 'scale_' + str(scale)
            for subsubdir in ['img_aligned', 'img_src']:
              subdir_path = os.path.join(destination_path,subdir,subsubdir)
              print_debug ( 70, "Deleting from a subdirectory named " + subdir_path )

              for al in scales_dict[scale]:
                try:
                  file_to_delete = os.path.join(subdir_path,os.path.basename(al.base_image_name))
                  print_debug ( 30, "Deleting " + file_to_delete )
                  os.remove ( file_to_delete )
                except:
                  # This will happen if the image had been deleted or hadn't been created (such as skipped).
                  pass

              try:
                print_debug ( 30, "Deleting " + subdir_path )
                os.remove ( subdir_path )
              except:
                # This will happen if the image had been deleted or hadn't been created (such as skipped).
                pass

              for al in scales_dict[scale]:
                al.image_dict['aligned'] = annotated_image(None, role='aligned')

        scales_dict = {}
        alignment_layer_index = 0
        alignment_layer_list = []
        current_scale = 1
        scales_dict[current_scale] = alignment_layer_list

      zpa_original.queue_draw()
      for p in panel_list:
        p.queue_draw()
      clear_all.destroy()

    elif command == "ClearOut":

      if len(destination_path) <= 0:
        clear_out = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="No Destination Set")
        response = clear_out.run()
        clear_out.destroy()
      else:
        clear_out = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="Remove All Output?")
        response = clear_out.run()
        if response == gtk.RESPONSE_OK:
          print_debug ( 20, "Clearing all output images..." )

          for scale in scales_dict.keys():
            print_debug ( 70, "Deleting images for scale " + str(scale) )
            if True or (scale != 1):
              subdir = 'scale_' + str(scale)
              subdir_path = os.path.join(destination_path,subdir,'img_aligned')
              print_debug ( 70, "Deleting from a subdirectory named " + subdir_path )

              for al in scales_dict[scale]:
                try:
                  file_to_delete = os.path.join(subdir_path,os.path.basename(al.base_image_name))
                  print_debug ( 30, "Deleting " + file_to_delete )
                  os.remove ( file_to_delete )
                except:
                  # This will happen if the image had been deleted or hadn't been created (such as skipped).
                  pass

              try:
                print_debug ( 30, "Deleting " + subdir_path )
                os.remove ( subdir_path )
              except:
                # This will happen if the image had been deleted or hadn't been created (such as skipped).
                pass

              for al in scales_dict[scale]:
                al.image_dict['aligned'] = annotated_image(None, role='aligned')

          for al in alignment_layer_list:
            try:
              file_to_delete = os.path.join(destination_path,os.path.basename(al.base_image_name))
              print_debug ( 30, "Deleting " + file_to_delete )
              os.remove ( file_to_delete )
            except:
              # This will happen if the image had been deleted or hadn't been created (such as skipped).
              pass
          print_debug ( 20, "Restoring original images..." )
          for al in alignment_layer_list:
            al.image_dict['aligned'] = annotated_image(None, role='aligned')
          zpa_original.queue_draw()
          for p in panel_list:
            p.queue_draw()
        clear_out.destroy()

    elif command == "LimZoom":

      zpa_original.max_zoom_count = 10
      zpa_original.min_zoom_count = -15
      for p in panel_list:
        p.max_zoom_count = zpa_original.max_zoom_count
        p.min_zoom_count = zpa_original.min_zoom_count

    elif command == "UnLimZoom":

      # This is now a toggle
      if zpa_original.max_zoom_count > 100:
        zpa_original.max_zoom_count = 10
        zpa_original.min_zoom_count = -15
      else:
        zpa_original.max_zoom_count = 1000
        zpa_original.min_zoom_count = -1500

      for p in panel_list:
        p.max_zoom_count = zpa_original.max_zoom_count
        p.min_zoom_count = zpa_original.min_zoom_count

    elif command == "UseCVersion":

      # This is a toggle
      if align_swiftir.global_swiftir_mode == 'python':
        align_swiftir.global_swiftir_mode = 'c'
      else:
        align_swiftir.global_swiftir_mode = 'python'

    elif command == "DoSwims":

      # This is a toggle
      if align_swiftir.global_do_swims == True:
        align_swiftir.global_do_swims = False
      else:
        align_swiftir.global_do_swims = True

    elif command == "DoCFMs":

      # This is a toggle
      if align_swiftir.global_do_cfms == True:
        align_swiftir.global_do_cfms = False
      else:
        align_swiftir.global_do_cfms = True

    elif command == "GenImgs":

      # This is a toggle
      if align_swiftir.global_gen_imgs == True:
        align_swiftir.global_gen_imgs = False
      else:
        align_swiftir.global_gen_imgs = True

    elif command == "Refresh":

      refresh_all_images()

    elif command == "ImCenter":

      print_debug ( 50, "Centering images" )
      center_all_images()

    elif command == "ActSize":

      print_debug ( 50, "Showing actual size" )
      show_all_actual_size()

    elif command == "WinCtrs":

      global show_window_centers
      show_window_centers = not show_window_centers
      print_debug ( 50, "Showing Window Centers is now " + str(show_window_centers) )
      zpa.queue_draw()
      for p in panel_list:
        p.drawing_area.queue_draw()

    elif command == "Affines":

      global show_window_affines
      show_window_affines = not show_window_affines
      print_debug ( 50, "Showing Window Affines is now " + str(show_window_affines) )
      zpa.queue_draw()
      for p in panel_list:
        p.drawing_area.queue_draw()

    elif command == "ShowSkipped":

      global show_skipped_layers
      show_skipped_layers = not show_skipped_layers

      for p in panel_list:
        p.move_through_stack ( 0 )
        p.drawing_area.queue_draw()

    elif command in [ x[0] for x in cursor_options ]:
      print_debug ( 50, "Got a cursor cursor change command: " + command )
      cmd_index = [ x[0] for x in cursor_options ].index(command)
      point_cursor = cursor_options[cmd_index][1]
      if point_mode:
        cursor = point_cursor
        zpa.set_cursor ( cursor )
        zpa.queue_draw()

    elif command == "PtMode":

      point_mode = not point_mode
      print_debug ( 50, "Point mode is now " + str(point_mode) )
      cursor = gtk.gdk.ARROW
      if point_mode:
        cursor = point_cursor
      #zpa.set_cursor ( cursor )
      #zpa.queue_draw()
      for p in panel_list:
        if p.point_add_enabled:
          p.set_cursor ( cursor )
          p.drawing_area.queue_draw()

    elif command == "PtDel":

      point_delete_mode = not point_delete_mode
      print_debug ( 50, "Point delete mode is now " + str(point_delete_mode) )
      cursor = gtk.gdk.ARROW
      if point_delete_mode:
        cursor = gtk.gdk.X_CURSOR
      for p in panel_list:
        if p.point_add_enabled:
          p.set_cursor ( cursor )
          p.drawing_area.queue_draw()

    elif command == "PtClear":

      print_debug ( 50, "Clearing all alignment points in this layer" )

      # Clear from dictionary
      al = alignment_layer_list[alignment_layer_index]
      al_keys = al.image_dict.keys()
      for im_index in range(len(al_keys)):
        print_debug ( 70, "Clearing out image index " + str(im_index) )
        im = al.image_dict[al_keys[im_index]]
        graphics_items = im.graphics_items
        # non_marker_items = [ gi for gi in graphics_items if (gi.marker == False) ]
        non_marker_items = []
        for gi in graphics_items:
          print_debug ( 90, "  Checking item " + str(gi) )
          if gi.marker == False:
            # This is not a marker ... so keep it
            non_marker_items.append ( gi )
          else:
            # This is a marker, so don't add it
            pass
        # Replace the list of graphics items with the reduced list:
        im.graphics_items = non_marker_items

      zpa.queue_draw()
      for p in panel_list:
        p.drawing_area.queue_draw()

    elif command == "DefWaves":

      label = gtk.Label("Wave Def: " + str(gui_fields.waves_dict))
      dialog = gtk.Dialog("Define Waves",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      waves_entry = gtk.Entry(2*len(str(gui_fields.waves_dict)))

      waves_entry.set_text ( str(gui_fields.waves_dict) )
      dialog.vbox.pack_end(waves_entry)
      waves_entry.show()

      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        print_debug ( 70, str(waves_entry.get_text()) )
        gui_fields.waves_dict = eval ( waves_entry.get_text() )
        print_debug ( 70, "Waves dict = " + str(gui_fields.waves_dict) )
        #gui_fields.scales_list = [ int(t) for t in gui_fields.scales_list if len(t) > 0 ]

        #update_menu_scales_from_gui_fields()

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      dialog.destroy()

    elif command == "Waves":

      # Create wavy versions of the aligned images
      print_debug ( 10, "Making Waves from Waves dict = " + str(gui_fields.waves_dict) )

      for scale in scales_dict.keys():
        print_debug ( 10, "Making waves at scale " + str(scale) )

        if True or (scale != 1):
          subdir = 'scale_' + str(scale)
          subdir_path = os.path.join(destination_path,subdir,'img_wave')
          print_debug ( 10, "Creating a subdirectory named " + subdir_path )
          try:
            os.mkdir ( subdir_path )
          except:
            # This catches directories that already exist
            pass

          #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
          first_pass = True
          for al in scales_dict[scale]:
            if 'aligned' in al.image_dict:
              img_rec = al.image_dict['aligned']
              if img_rec.image != None:
                img = img_rec.image
                h = img.get_height()
                w = img.get_width()

                # Make a mir script

                mir_script  = ''
                mir_script += 'F ' + img_rec.file_name + os.linesep

                if first_pass:
                  mir_script += 'R' + os.linesep
                else:
                  # The following layers will all become wavy
                  R = gui_fields.waves_dict['R']
                  C = gui_fields.waves_dict['C']
                  A = gui_fields.waves_dict['A']
                  F = gui_fields.waves_dict['F']

                  # Write the points for the mir script
                  for yi in range(R):
                    ypre = yi * h / (R-1)
                    ypost = ypre + 0
                    for xi in range(C):
                      xpre = xi * w / (C-1)
                      xpost = xpre + ((w*A) * math.sin(F*math.pi*yi/R))
                      mir_script += "%d %d %d %d" % (xpost, ypost, xpre, ypre) + os.linesep
                  mir_script += 'T' + os.linesep

                  # Write the triangles for the mir script
                  for yi in range(R-1):
                    yleft = yi * C
                    for xi in range(C-1):
                      mir_script += "%d %d %d" % (yleft+xi, yleft+C+xi, yleft+xi+1) + os.linesep
                      mir_script += "%d %d %d" % (yleft+xi+C+1, yleft+xi+1,yleft+C+xi) + os.linesep

                # Write the "Write" command for the mir script
                mir_script += 'W ' + os.path.join(subdir_path,os.path.basename(al.base_image_name)) + os.linesep

                print ( mir_script )

                # Run the actual mir script
                align_swiftir.run_command ( "mir", arg_list=[], cmd_input=mir_script )
                first_pass = False

    elif command == "DefGrid":

      label = gtk.Label("Grid Def: " + str(gui_fields.grid_dict))
      dialog = gtk.Dialog("Define Grid",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      grid_entry = gtk.Entry(2*len(str(gui_fields.grid_dict)))

      grid_entry.set_text ( str(gui_fields.grid_dict) )
      dialog.vbox.pack_end(grid_entry)
      grid_entry.show()

      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        print_debug ( 70, str(grid_entry.get_text()) )
        gui_fields.grid_dict = eval ( grid_entry.get_text() )
        print_debug ( 70, "Grid dict = " + str(gui_fields.grid_dict) )
        #gui_fields.scales_list = [ int(t) for t in gui_fields.scales_list if len(t) > 0 ]

        #update_menu_scales_from_gui_fields()

        # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      dialog.destroy()

    elif command == "Grid":

      # Generate aligned versions of the wavy images
      print_debug ( 10, "Making Grid Alignment" )

      for scale in scales_dict.keys():
        print_debug ( 10, "Making grid alignment at scale " + str(scale) )

        if True or (scale != 1):
          subdir = 'scale_' + str(scale)
          subdir_path = os.path.join(destination_path,subdir,'img_grid')
          print_debug ( 10, "Creating a subdirectory named " + subdir_path )
          try:
            os.mkdir ( subdir_path )
          except:
            # This catches directories that already exist
            pass

          f1 = None
          f2 = None

          for al in scales_dict[scale]:

            if 'aligned' in al.image_dict:
              img_rec = al.image_dict['aligned']
              if img_rec.image != None:
                img = img_rec.image
                h = img.get_height()
                w = img.get_width()

                f2 = img_rec.file_name

                if f1 == None:

                  # This is the first image so just copy it
                  mir_script  = ''
                  mir_script += 'F ' + f2 + os.linesep
                  mir_script += 'R' + os.linesep
                  mir_script += 'W ' + os.path.join(subdir_path,os.path.basename(f2)) + os.linesep

                  # print ( mir_script )

                  align_swiftir.run_command ( "mir", arg_list=[], cmd_input=mir_script )

                else:

                  # This is a following image so align it

                  N = 10
                  ww = 32
                  if 'N' in gui_fields.grid_dict:
                    N = gui_fields.grid_dict['N']
                  if 'ww' in gui_fields.grid_dict:
                    ww = gui_fields.grid_dict['ww']

                  # Calculate the points list and triangles

                  R = N
                  C = N
                  points = []
                  for yi in range(R):
                    ypre = yi * h / (R-1)
                    for xi in range(C):
                      xpre = xi * w / (C-1)
                      # Put the same x,y pair in both parts of the array for now
                      points.append ( [xpre, ypre, xpre, ypre] )

                  triangles = []
                  for yi in range(R-1):
                    yleft = yi * C
                    for xi in range(C-1):
                      triangles.append ( (yleft+xi, yleft+C+xi, yleft+xi+1) )
                      triangles.append ( (yleft+xi+C+1, yleft+xi+1,yleft+C+xi) )

                  # Make a script to run swim at each point

                  swim_script = ""
                  for p in points:
                    swim_script += "swim -i 2 -x 0 -y 0 " + f1 + " " + str(p[0]) + " " + str(p[1]) + " " + f2 + " " + str(p[0]) + " " + str(p[1]) + os.linesep

                  print ( "\n=========== Swim Script ============\n" + str(swim_script) + "============================\n" )
                  o = align_swiftir.run_command ( "swim", arg_list=[str(ww)], cmd_input=swim_script )
                  swim_out_lines = o['out'].strip().split('\n')
                  swim_err_lines = o['err'].strip().split('\n')

                  if len(swim_out_lines) != len(points):
                    print ( "!!!! Warning: Output didn't match input" )
                    exit()

                  print ( "\nRaw Output:\n" )
                  for ol in swim_out_lines:
                    print ( "  " + str(ol) )

                  print ( "\nX Offset:\n" )
                  for ol in swim_out_lines:
                    parts = ol.replace('(',' ').replace(')',' ').strip().split()
                    print ( "  " + str(parts[8]) )

                  # Update the points array to include the deltas from swim in the first x,y pair

                  for i in range(len(points)):
                    ol = swim_out_lines[i]
                    parts = ol.replace('(',' ').replace(')',' ').strip().split()
                    dx = float(parts[8])
                    dy = float(parts[9])
                    points[i] = [ points[i][0]-dx, points[i][1]-dy, points[i][2], points[i][3] ]

                  # Make a script to run mir with the new point pairs

                  mir_script  = ''
                  mir_script += 'F ' + f2 + os.linesep

                  for pt in points:
                    mir_script += "%d %d %d %d" % (pt[0], pt[1], pt[2], pt[3]) + os.linesep
                  mir_script += 'T' + os.linesep

                  for tri in triangles:
                    mir_script += "%d %d %d" % (tri[0], tri[1], tri[2]) + os.linesep

                  mir_script += 'W ' + os.path.join(subdir_path,os.path.basename(f2)) + os.linesep

                  # print ( mir_script )

                  align_swiftir.run_command ( "mir", arg_list=[], cmd_input=mir_script )

                f1 = f2

    elif command == "SWaves":

      # Show the wavy images
      print_debug ( 10, "Showing Wavy Images" )

      for scale in scales_dict.keys():

        if True or (scale != 1):
          subdir = 'scale_' + str(scale)
          subdir_path = os.path.join(destination_path,subdir,'img_wave')

          f1 = None
          f2 = None

          for al in scales_dict[scale]:
            al.image_dict['aligned'] = annotated_image ( os.path.join(subdir_path,os.path.basename(al.image_dict['aligned'].file_name)), role=al.image_dict['aligned'].role )

      zpa.queue_draw()
      for p in panel_list:
        p.drawing_area.queue_draw()

    elif command == "SGrid":

      # Show the grid images
      print_debug ( 10, "Showing Grid Aligned Images" )

      for scale in scales_dict.keys():

        if True or (scale != 1):
          subdir = 'scale_' + str(scale)
          subdir_path = os.path.join(destination_path,subdir,'img_grid')

          f1 = None
          f2 = None

          for al in scales_dict[scale]:
            al.image_dict['aligned'] = annotated_image ( os.path.join(subdir_path,os.path.basename(al.image_dict['aligned'].file_name)), role=al.image_dict['aligned'].role )

      zpa.queue_draw()
      for p in panel_list:
        p.drawing_area.queue_draw()

    elif command == "SAligned":

      # Show the normal aligned images
      print_debug ( 10, "Showing Normal Aligned Images" )

      for scale in scales_dict.keys():

        if True or (scale != 1):
          subdir = 'scale_' + str(scale)
          subdir_path = os.path.join(destination_path,subdir,'img_aligned')

          f1 = None
          f2 = None

          for al in scales_dict[scale]:
            al.image_dict['aligned'] = annotated_image ( os.path.join(subdir_path,os.path.basename(al.image_dict['aligned'].file_name)), role=al.image_dict['aligned'].role )

      zpa.queue_draw()
      for p in panel_list:
        p.drawing_area.queue_draw()

    elif command == "Structs":

      print_data_structures(panel_list, alignment_layer_list)

    elif command == "DefPlotCode":

      print_debug ( 70, "Set to Default Plotting Code" )
      current_plot_code = default_plot_code.strip()

      if code_dialog != None:
        print_debug ( 70, "Creating the plot code dialog" )
        code_store.set_text ( current_plot_code )

    elif command == "PlotCode":

      print_debug ( 70, "Modify Plotting Code" )

      if len(current_plot_code) <= 0:
        current_plot_code = default_plot_code.strip()

      if code_dialog == None:
        print_debug ( 70, "Creating the plot code dialog" )
        #label = gtk.Label("Enter plotting code:")
        code_dialog = gtk.Dialog("Plot Code", None,
                           gtk.DIALOG_DESTROY_WITH_PARENT,
                           #(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                            (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
        #code_dialog.vbox.pack_start(label)
        #label.show()
        code_store = gtk.TextBuffer()

        code_store.set_text ( current_plot_code )

        code_entry = gtk.TextView(buffer=code_store)

        #scales_entry = gtk.Entry(20)
        #scales_entry.set_text ( str ( ' '.join ( [ str(n) for n in gui_fields.scales_list ] ) ) )
        code_dialog.vbox.pack_end(code_entry)
        code_entry.show()

      print_debug ( 70, "before run" )
      response = code_dialog.run()
      print_debug ( 70, "after run" )
      # response = None
      if response == gtk.RESPONSE_ACCEPT:
        print_debug ( 70, "Updating current plot code from dialog" )
        bi = code_store.get_iter_at_offset(0)
        ei = code_store.get_iter_at_offset(-1)
        txt = code_store.get_text(bi,ei)
        current_plot_code = txt.strip()

        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      #code_dialog.destroy()


    elif command == "PlotExec":

      print_debug ( 70, "Plotting ..." )

      if code_store != None:
        bi = code_store.get_iter_at_offset(0)
        ei = code_store.get_iter_at_offset(-1)
        txt = code_store.get_text(bi,ei)
        current_plot_code = txt.strip()

      exec_code = current_plot_code
      if len(exec_code) <= 0:
        exec_code = default_plot_code

      fb = StringBufferFile()
      write_json_project ( project_file_name, fb=fb )
      if len(fb.fs.strip()) > 0:
        try:
          d = json.loads ( fb.fs )
          if (exec_code != None) and (len(exec_code) > 0):
            # Run the current plot code
            exec ( exec_code, locals() )
        except:
          print_debug ( 1, "Error when plotting" )


    elif command == "Exit":

      get_exit = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="Exit?")
      response = get_exit.run()
      if response == gtk.RESPONSE_OK:
        print_debug ( 50, "Exiting." )
        get_exit.destroy()
        exit()
      get_exit.destroy()

    elif command.startswith ('Level '):

      global debug_level
      debug_level = int(command[6:])
      print_debug ( -1, "Changing debug level from " + str(align_swiftir.debug_level) + " to " + str(debug_level) )
      align_swiftir.debug_level = debug_level

    else:

      print_debug ( 20, "Menu option \"" + command + "\" is not handled yet." )

  return True


# Do Linear Regression of X,Y data
def lin_fit(x,y):

  (m,b,r,p,stderr) = sps.linregress(x,y)
#  print('linear regression:')
#  print('  slope:',m)
#  print('  intercept:',b)
#  print('  r:',r)
#  print('  p:',p)
#  print('  stderr:',stderr)
#  print('')

  return(m,b,r,p,stderr)

def show_all_actual_size():
  global panel_list
  global alignment_layer_list
  print_debug ( 50, "show_all_actual_size called with len(alignment_layer_index) = " + str(len(alignment_layer_list)) )
  if len(alignment_layer_list) > 0:
    # Apply to each of the panel images
    for panel in panel_list:
      panel.set_defaults()
      panel.queue_draw()

def center_all_images():
  global panel_list
  global alignment_layer_list
  print_debug ( 50, "center_all_images called with len(alignment_layer_index) = " + str(len(alignment_layer_list)) )
  if len(alignment_layer_list) > 0:
    # Center each of the panel images
    print_debug ( 50, "Begin looping through all " + str(len(panel_list)) + " panels" )
    max_win = [1,1]
    for panel in panel_list:
      panel.queue_draw()
      win_size = panel.drawing_area.window.get_size()
      if max_win[0] < win_size[0]:
         max_win[0] = win_size[0]
      if max_win[1] < win_size[1]:
         max_win[1] = win_size[1]
    win_size = max_win
    for panel in panel_list:
      print_debug ( 70, "  window size = " + str(win_size) )
      pix_buf = None
      wxh = None
      # Loop through all layers looking for images matching this role
      print_debug ( 70, "  Begin looping through all " + str(len(alignment_layer_list)) + " layers" )
      for layer in alignment_layer_list:
        print_debug ( 80, "    Checking for role " + str(panel.role) )
        if panel.role in layer.image_dict:
          print_debug ( 80, "      Role " + str(panel.role) + " was found" )
          # This panel's role is implemented by an image in this layer
          pix_buf = layer.image_dict[panel.role].image
          print_debug ( 80, "      Loaded pix_buf = " + str(pix_buf) )
          if type(pix_buf) != type(None):
            if type(wxh) == type(None):
               wxh = [0,0]
            if wxh[0] < pix_buf.get_width():
               wxh[0] = pix_buf.get_width()
            if wxh[1] < pix_buf.get_height():
               wxh[1] = pix_buf.get_height()
      if type(wxh) != type(None):
        print_debug ( 70, "  For panel " + str(panel_list.index(panel)) + " image size is: [" + str(wxh[0]) + " x " + str(wxh[1]) + "]" )
        # pix_buf = alignment_layer_list[alignment_layer_index].image_dict[panel.role].image
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        panel.set_scale_to_fit ( 0, wxh[0], 0, wxh[1], win_size[0], win_size[1] )
        panel.queue_draw()
        print_debug ( 70, "  Panel " + str(panel_list.index(panel)) + " is set to: [" + str(wxh[0]) + " x " + str(wxh[1]) + "] in [" + str(win_size[0]) + "," + str(win_size[1]) + "]" )
        print_debug ( 70, "")


def refresh_all_images():
  # Determine how many panels are needed and create them as needed
  global panel_list
  global scales_dict
  max_extra_panels = 0

  panel_names_list = ['ref', 'base']

  # Scan through all scales and all images to get the required set of roles (panel_names)
  for scale_key in sorted(scales_dict.keys()):
    align_layer_list_for_scale = scales_dict[scale_key]
    if align_layer_list_for_scale != None:
      for a in align_layer_list_for_scale:
        for k in a.image_dict.keys():
          if not (k in panel_names_list):
            panel_names_list.append ( k )

  print_debug ( 70, "Panel names list = " + str(panel_names_list) )

  # Create a new panel list to eventually replace the old panel_list
  new_panel_list = []

  # Pull out the first panel of each type if it exists
  for name in panel_names_list:
    print_debug ( 70, "Looking for name " + name )
    for current_panel in panel_list:
      print_debug ( 70, "  Checking current_panel with role of " + current_panel.role )
      if current_panel.role == name:
        print_debug ( 70, "    This panel matched" )
        new_panel_list.append ( current_panel )
        panel_list.remove ( current_panel )
        break
  print_debug ( 70, "old_panel_list roles: " + str([p.role for p in panel_list]) )
  print_debug ( 70, "new_panel_list roles: " + str([p.role for p in new_panel_list]) )

  # Figure out which panels need to be deleted
  panels_to_delete = []
  for old_panel in panel_list:
    if not (old_panel in new_panel_list):
      panels_to_delete.append ( old_panel )

  # Delete the GTK drawing areas for panels to be removed
  for p in panels_to_delete:
    global image_hbox
    image_hbox.remove(p.drawing_area)

  # Assign the new_panel_list to be the global panel_list
  panel_list = new_panel_list

  print_debug ( 70, "final_panel_list roles: " + str([p.role for p in panel_list]) )


# Create the window and connect the events
def main_gtk_version():

  global gui_fields
  global window
  global menu_bar
  global panel_list

  # Create a top-level GTK window
  window = gtk.Window ( gtk.WINDOW_TOPLEVEL )
  window.set_title ( "Python GTK version of SWiFT-GUI" )

  # Create a zoom/pan area to hold all of the drawing

  global zpa_original
  zpa_original = zoom_panel(window,global_win_width,global_win_height,"base",point_add_enabled=True)
  zpa_original.force_center = True

  global panel_list
  panel_list.append ( zpa_original )

  zpa_original.user_data = {
                    'image_frame'        : None,
                    'image_frames'       : [],
                    'frame_number'       : -1,
                    'running'            : False,
                    'last_update'        : -1,
                    'show_legend'        : True,
                    'frame_delay'        : 0.1,
                    'size'               : 1.0
                  }

  # Set the relationships between "user" coordinates and "screen" coordinates

  zpa_original.set_x_scale ( 0.0, 300, 100.0, 400 )
  zpa_original.set_y_scale ( 0.0, 250 ,100.0, 350 )

  # Create a vertical box to hold the menu, drawing area, and buttons
  main_win_vbox = gtk.VBox ( homogeneous=False, spacing=0 )
  window.add(main_win_vbox)
  main_win_vbox.show()

  # Connect GTK's "main_quit" function to the window's "destroy" event
  window.connect ( "destroy", lambda w: gtk.main_quit() )

  # Create a menu bar and add it to the vertical box
  menu_bar = gtk.MenuBar()
  main_win_vbox.pack_start(menu_bar, expand=False, fill=False, padding=0)

  global cursor_options
  global cursor_option_seps

  # Create a "File" menu
  (file_menu, file_item) = zpa_original.add_menu ( "_File" )
  if True: # An easy way to indent and still be legal Python
    this_menu = file_menu
    zpa_original.add_menu_item ( this_menu, menu_callback, "New Project",  ("NewProj", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Open Project",  ("OpenProj", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Save Project",  ("SaveProj", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Save Project As...",  ("SaveProjAs", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Set Destination",  ("SetDest", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    # zpa_original.add_menu_item ( this_menu, menu_callback, "List >",  ("List", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Exit",       ("Exit", zpa_original ) )

  # Create an "Images" menu
  (image_menu, image_item) = zpa_original.add_menu ( "_Images" )
  if True: # An easy way to indent and still be legal Python
    this_menu = image_menu
    zpa_original.add_menu_item ( this_menu, menu_callback, "Import...",  ("ImImport", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Center",  ("ImCenter", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Actual Size",  ("ActSize", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Refresh",  ("Refresh", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Clear Out Images",  ("ClearOut", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Clear All Layers",  ("ClearLayers", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Clear Everything",  ("ClearEverything", zpa_original ) )

  # Create a "Scaling" menu
  (scaling_menu, scaling_item) = zpa_original.add_menu ( "Scalin_g" )
  if True: # An easy way to indent and still be legal Python
    this_menu = scaling_menu
    zpa_original.add_menu_item ( this_menu, menu_callback, "Define Scales",  ("DefScales", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Generate All Scales",  ("GenAllScales", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Import All Scales",  ("ImportAllScales", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Generate Tiled",   ("GenAsTiled", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Import Tiled",   ("ImportTiled", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Show Tiled",   ("ShowTiled", zpa_original ) )
    '''
    # These aren't useful yet, so hide them for now ...
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Generate Missing",  ("GenMissingScales", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Delete All Scales",  ("DelAllScales", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Delete Missing Scales",  ("DelMissingScales", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    '''

  # Create a "Scales" menu
  (scales_menu, scales_item) = zpa_original.add_menu ( "_Scales" )
  if True: # An easy way to indent and still be legal Python
    this_menu = scales_menu
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Scale 1",   ("SelectScale_1", zpa_original ), default=True )

  # Create a "Points" menu
  (points_menu, points_item) = zpa_original.add_menu ( "_Points" )
  if True: # An easy way to indent and still be legal Python
    this_menu = points_menu
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Alignment Point Mode",   ("PtMode", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Delete Points",   ("PtDel", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Clear All Alignment Points",   ("PtClear", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    # Create a "Set/Cursor" submenu for point mode only
    # This didn't work ...
    #  (cursor_menu, set_item) = this_menu.add_menu_item ( "_Cursor" )
    #  if True: # An easy way to indent and still be legal Python
    # So put in the main menu for now:
    # Add cursors from the "cursor_options" array
    cursor_index = 0
    cbox_group = None
    for cursor_pair in cursor_options:
      cursor_option_string = cursor_pair[0]
      selected = False
      if cbox_group is None:
        selected = True
      val = zpa_original.add_radiomenu_item ( this_menu, menu_callback, cursor_option_string[len('Cursor_'):],   (cursor_option_string, zpa_original ), group=cbox_group, default=selected )
      if cbox_group == None:
        cbox_group = val
      if cursor_index in cursor_option_seps:
        zpa_original.add_menu_sep  ( this_menu )
      cursor_index += 1

  # Create a "Set" menu
  (set_menu, set_item) = zpa_original.add_menu ( "_Set" )
  if True: # An easy way to indent and still be legal Python
    this_menu = set_menu
    # zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Limited Zoom",   ("LimZoom", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Max Image Size",   ("MaxFileSize", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Perform Swims",   ("DoSwims", zpa_original ), default=align_swiftir.global_do_swims )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Update CFMs",   ("DoCFMs", zpa_original ), default=align_swiftir.global_do_cfms )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Generate Images",   ("GenImgs", zpa_original ), default=align_swiftir.global_gen_imgs )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Use C Version",   ("UseCVersion", zpa_original ), default=False )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "UnLimited Zoom",   ("UnLimZoom", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Default Plot Code",   ("DefPlotCode", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Custom Plot Code",   ("PlotCode", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )

  # Create a "Debug" menu
  (debug_menu, debug_item) = zpa_original.add_menu ( "_Debug" )
  if True: # An easy way to indent and still be legal Python
    this_menu = debug_menu
    zpa_original.add_menu_item ( this_menu, menu_callback, "Python Console",   ("Debug", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Print Affine",   ("Affine", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Print Structures",   ("Structs", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Define Waves",    ("DefWaves", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Make Waves",   ("Waves", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Define Grid",    ("DefGrid", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Grid Align",   ("Grid", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )

    cbox_group = zpa_original.add_radiomenu_item ( this_menu, menu_callback, "Show Waves",   ("SWaves", zpa_original ), group=None, default=False )
    zpa_original.add_radiomenu_item ( this_menu, menu_callback, "Show Grid Align",    ("SGrid", zpa_original ), group=cbox_group, default=False )
    zpa_original.add_radiomenu_item ( this_menu, menu_callback, "Show Aligned",    ("SAligned", zpa_original ), group=cbox_group, default=True )
    zpa_original.add_menu_sep  ( this_menu )
    cbox_group = None
    global debug_level
    for level in [ 10*x for x in range(0,11) ]:
      selected = False
      if (level>=debug_level) and (level<(debug_level+10)):
        selected = True
      val = zpa_original.add_radiomenu_item ( this_menu, menu_callback, "Level " + str(level),   ("Level " + str(level), zpa_original ), group=cbox_group, default=selected )
      if cbox_group == None:
        cbox_group = val

  # Create a "Show" menu
  (show_menu, show_item) = zpa_original.add_menu ( "_Show" )
  if True: # An easy way to indent and still be legal Python
    this_menu = show_menu
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Window Centers",   ("WinCtrs", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Affines",   ("Affines", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Skipped Images",   ("ShowSkipped", zpa_original ), default=True )
    global plotting_available
    if plotting_available:
      # Only show this menu option if all of the plotting libraries have been found
      zpa_original.add_menu_sep  ( this_menu )
      zpa_original.add_menu_item ( this_menu, menu_callback, "Plot",   ("PlotExec", zpa_original ) )

  # Create a "Help" menu
  (help_menu, help_item) = zpa_original.add_menu ( "_Help" )
  if True: # An easy way to indent and still be legal Python
    this_menu = help_menu
    zpa_original.add_menu_item ( this_menu, menu_callback, "Manual...",   ("Manual", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Key commands...",   ("Key Commands", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Mouse clicks...",   ("Mouse Clicks", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "License...",   ("License", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Version...",   ("Version", zpa_original ) )

  # Append the menus to the menu bar itself
  menu_bar.append ( file_item )
  menu_bar.append ( image_item )
  menu_bar.append ( scaling_item )
  menu_bar.append ( scales_item )
  menu_bar.append ( points_item )
  menu_bar.append ( set_item )
  menu_bar.append ( show_item )
  menu_bar.append ( debug_item )
  menu_bar.append ( help_item )

  # Show the menu bar itself (everything must be shown!!)
  menu_bar.show()

  # Create the horizontal image box
  global image_hbox
  image_hbox = gtk.HBox ( True, 0 )
  panel_list = []

  # The zoom/pan area has its own drawing area (that it zooms and pans)
  original_drawing_area = zpa_original.get_drawing_area()

  panel_list.append ( zpa_original )

  # Add the zoom/pan area to the vertical box (becomes the main area)
  image_hbox.pack_start(original_drawing_area, True, True, 0)

  image_hbox.show()
  main_win_vbox.pack_start(image_hbox, True, True, 0)
  original_drawing_area.show()

  # The zoom/pan area doesn't draw anything, so add our custom expose callback
  original_drawing_area.connect ( "expose_event", zpa_original.expose_callback, zpa_original )

  # Set the events that the zoom/pan area must respond to
  #  Note that zooming and panning requires button press and pointer motion
  #  Other events can be set and handled by user code as well
  original_drawing_area.set_events ( gtk.gdk.EXPOSURE_MASK
                                   | gtk.gdk.LEAVE_NOTIFY_MASK
                                   | gtk.gdk.BUTTON_PRESS_MASK
                                   | gtk.gdk.POINTER_MOTION_MASK
                                   | gtk.gdk.POINTER_MOTION_HINT_MASK )

  alignment_layer_defaults = alignment_layer()

  # Create a Vertical box to hold rows of buttons
  controls_vbox = gtk.VBox ( True, 10 )
  controls_vbox.show()
  main_win_vbox.pack_start ( controls_vbox, False, False, 0 )

  # Add some rows of application specific controls and their callbacks

  # Create a horizontal box to hold a row of controls

  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )
  gui_fields.proj_label = gtk.Label("Project File: " + str(project_file_name))
  controls_hbox.pack_start ( gui_fields.proj_label, True, True, 0 )
  gui_fields.proj_label.show()

  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )
  gui_fields.dest_label = gtk.Label("Destination: " + str(destination_path))
  controls_hbox.pack_start ( gui_fields.dest_label, True, True, 0 )
  gui_fields.dest_label.show()


  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )


  label_entry = gtk.HBox ( False, 5 )
  button = gtk.Button("Jump To:")
  label_entry.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", jump_to_callback, zpa_original )
  button.show()
  gui_fields.jump_to_index = gtk.Entry(6)
  gui_fields.jump_to_index.set_text ( '1' )
  label_entry.pack_start ( gui_fields.jump_to_index, True, True, 0 )
  gui_fields.jump_to_index.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  '''
  a_label = gtk.Label("Translation Pass:")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  # The variable "label_entry" is used for a transient hbox containing a label and an entry
  # The variable
  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("WW:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  '''
  gui_fields.trans_ww_entry = gtk.Entry(5)
  gui_fields.trans_ww_entry.set_text ( '0' )
  '''
  gui_fields.trans_ww_entry.set_text ( str(alignment_layer_defaults.trans_ww) )
  label_entry.pack_start ( gui_fields.trans_ww_entry, True, True, 0 )
  gui_fields.trans_ww_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addx:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  '''
  gui_fields.trans_addx_entry = gtk.Entry(6)
  gui_fields.trans_addx_entry.set_text ( '0' )
  '''
  gui_fields.trans_addx_entry.set_text ( str(alignment_layer_defaults.trans_addx) )
  label_entry.pack_start ( gui_fields.trans_addx_entry, True, True, 0 )
  gui_fields.trans_addx_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addy:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  '''
  gui_fields.trans_addy_entry = gtk.Entry(6)
  gui_fields.trans_addy_entry.set_text ( '0' )
  '''
  gui_fields.trans_addy_entry.set_text ( str(alignment_layer_defaults.trans_addy) )
  label_entry.pack_start ( gui_fields.trans_addy_entry, True, True, 0 )
  gui_fields.trans_addy_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()
  '''


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label(" ")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.skip_check_box = gtk.CheckButton("Skip")
  gui_fields.skip_check_box.connect_object ( "clicked", change_skip_callback, False )
  label_entry.pack_start ( gui_fields.skip_check_box, True, True, 0 )
  gui_fields.skip_check_box.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()

  button = gtk.Button("Clear All Skips")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", clear_all_skips_callback, False )
  button.show()

  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label(" ")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  #junk_skip_check_box = gtk.ComboBox("Alignment")
  gui_fields.align_method_select = gtk.ComboBox()
  store = gtk.ListStore(str)
  cell = gtk.CellRendererText()
  gui_fields.align_method_select.pack_start(cell)
  gui_fields.align_method_select.add_attribute(cell, 'text', 0)
  store.append ( ['Auto Swim Align'] )
  store.append ( ['Match Point Align'] )
  gui_fields.align_method_select.set_model(store)
  gui_fields.align_method_select.set_active(0)
  label_entry.pack_start ( gui_fields.align_method_select, True, True, 0 )
  gui_fields.align_method_select.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  '''
  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )

  a_label = gtk.Label(" ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  '''
  gui_fields.affine_check_box = gtk.CheckButton("  Affine Pass:")
  gui_fields.affine_check_box.set_active(True)
  '''
  gui_fields.affine_check_box.set_active(True)
  controls_hbox.pack_start ( gui_fields.affine_check_box, True, True, 0 )
  gui_fields.affine_check_box.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("WW:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  '''
  gui_fields.affine_ww_entry = gtk.Entry(5)
  gui_fields.affine_ww_entry.set_text ( '0' )
  '''
  gui_fields.affine_ww_entry.set_text ( str(alignment_layer_defaults.affine_ww) )
  label_entry.pack_start ( gui_fields.affine_ww_entry, True, True, 0 )
  gui_fields.affine_ww_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addx:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  '''
  gui_fields.affine_addx_entry = gtk.Entry(6)
  gui_fields.affine_addx_entry.set_text ( '0' )
  '''
  gui_fields.affine_addx_entry.set_text ( str(alignment_layer_defaults.affine_addx) )
  label_entry.pack_start ( gui_fields.affine_addx_entry, True, True, 0 )
  gui_fields.affine_addx_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addy:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  '''
  gui_fields.affine_addy_entry = gtk.Entry(6)
  gui_fields.affine_addy_entry.set_text ( '0' )
  '''
  gui_fields.affine_addy_entry.set_text ( str(alignment_layer_defaults.affine_addy) )
  label_entry.pack_start ( gui_fields.affine_addy_entry, True, True, 0 )
  gui_fields.affine_addy_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  a_label = gtk.Label(" ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()
  '''



  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )

  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("SNR Skip:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.snr_skip = gtk.Entry(6)
  gui_fields.snr_skip.set_text ( '' )
  label_entry.pack_start ( gui_fields.snr_skip, True, True, 0 )
  gui_fields.snr_skip.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  button = gtk.Button("All SNR Skip -> Skip")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", snr_skip_to_skip_callback, False )
  button.show()

  button = gtk.Button("Clear SNR Skips")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", clear_snr_skip_to_skip_callback, False )
  button.show()

  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("SNR Halt:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.snr_halt = gtk.Entry(6)
  gui_fields.snr_halt.set_text ( '' )
  label_entry.pack_start ( gui_fields.snr_halt, True, True, 0 )
  gui_fields.snr_halt.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()



  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )

  # Create the code_base_select control (selects how to run)
  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label(" ")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  #junk_skip_check_box = gtk.ComboBox("Alignment")
  gui_fields.code_base_select = gtk.ComboBox()
  store = gtk.ListStore(str)
  cell = gtk.CellRendererText()
  gui_fields.code_base_select.pack_start(cell)
  gui_fields.code_base_select.add_attribute(cell, 'text', 0)
  # Hard-coded alignment runners
  store.append ( ['Internal Swim Align'] )
  store.append ( ['External Swim Align'] )
  # Dynamic alignment runners
  runner_files = [ f for f in os.listdir(".") if f.startswith('pyswift_run_') and f.endswith('.py') ]
  runner_files = [ f for f in runner_files if f != "pyswift_run_external.py" ]
  runner_files = sorted(runner_files)
  print_debug ( 70, "Runner files = " + str(runner_files) )
  for f in runner_files:
    store.append ( [ f ] )
  gui_fields.code_base_select.set_model(store)
  gui_fields.code_base_select.set_active(0)
  label_entry.pack_start ( gui_fields.code_base_select, True, True, 0 )
  gui_fields.code_base_select.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  a_label = gtk.Label(" Bias Pass:  ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  gui_fields.bias_check_box = gtk.CheckButton("  Bias Pass:")
  #controls_hbox.pack_start ( gui_fields.bias_check_box, True, True, 0 )
  #gui_fields.bias_check_box.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("dx per image:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.bias_dx_entry = gtk.Entry(5)
  gui_fields.bias_dx_entry.set_text ( str(alignment_layer_defaults.bias_dx) )
  label_entry.pack_start ( gui_fields.bias_dx_entry, True, True, 0 )
  gui_fields.bias_dx_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("dy per image:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.bias_dy_entry = gtk.Entry(5)
  gui_fields.bias_dy_entry.set_text ( str(alignment_layer_defaults.bias_dy) )
  label_entry.pack_start ( gui_fields.bias_dy_entry, True, True, 0 )
  gui_fields.bias_dy_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  a_label = gtk.Label(" ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )

  # Create the init_refine_apply control (selects how to run)
  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label(" ")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()

  gui_fields.init_refine_apply_entry = gtk.ComboBox()
  store = gtk.ListStore(str)
  cell = gtk.CellRendererText()
  gui_fields.init_refine_apply_entry.pack_start(cell)
  gui_fields.init_refine_apply_entry.add_attribute(cell, 'text', 0)
  # Options
  store.append ( ['Init Affine'] )
  store.append ( ['Refine Affine'] )
  store.append ( ['Apply Affine'] )
  # Dynamic alignment runners
  gui_fields.init_refine_apply_entry.set_model(store)
  gui_fields.init_refine_apply_entry.set_active(0)
  label_entry.pack_start ( gui_fields.init_refine_apply_entry, True, True, 0 )
  gui_fields.init_refine_apply_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  a_label = gtk.Label(" Biases:  ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  gui_fields.bias_check_box = gtk.CheckButton("  Bias Pass:")
  #controls_hbox.pack_start ( gui_fields.bias_check_box, True, True, 0 )
  #gui_fields.bias_check_box.show()

  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("rotation:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.bias_rotation_entry = gtk.Entry(5)
  gui_fields.bias_rotation_entry.set_text ( str(alignment_layer_defaults.bias_rotation) )
  label_entry.pack_start ( gui_fields.bias_rotation_entry, True, True, 0 )
  gui_fields.bias_rotation_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()

  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("scale_x:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.bias_scale_x_entry = gtk.Entry(5)
  gui_fields.bias_scale_x_entry.set_text ( str(alignment_layer_defaults.bias_scale_x) )
  label_entry.pack_start ( gui_fields.bias_scale_x_entry, True, True, 0 )
  gui_fields.bias_scale_x_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()

  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("scale_y:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.bias_scale_y_entry = gtk.Entry(5)
  gui_fields.bias_scale_y_entry.set_text ( str(alignment_layer_defaults.bias_scale_y) )
  label_entry.pack_start ( gui_fields.bias_scale_y_entry, True, True, 0 )
  gui_fields.bias_scale_y_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()

  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("skew_x:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.bias_skew_x_entry = gtk.Entry(5)
  gui_fields.bias_skew_x_entry.set_text ( str(alignment_layer_defaults.bias_skew_x) )
  label_entry.pack_start ( gui_fields.bias_skew_x_entry, True, True, 0 )
  gui_fields.bias_skew_x_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  a_label = gtk.Label(" ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()


  '''
  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )

  button = gtk.Button("Set All")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", set_all_or_fwd_callback, True )
  button.show()

  button = gtk.Button("Set Forward")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", set_all_or_fwd_callback, False )
  button.show()


  label_entry = gtk.HBox ( False, 5 )
  button = gtk.Button("Jump To:")
  label_entry.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", jump_to_callback, zpa_original )
  button.show()
  gui_fields.jump_to_index = gtk.Entry(6)
  gui_fields.jump_to_index.set_text ( '1' )
  label_entry.pack_start ( gui_fields.jump_to_index, True, True, 0 )
  gui_fields.jump_to_index.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()
  '''



  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )

  button = gtk.Button("Align All")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", run_alignment_callback, True )
  button.show()

  button = gtk.Button("Align Forward")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", run_alignment_callback, False )
  button.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("# Forward")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.num_align_forward = gtk.Entry(6)
  gui_fields.num_align_forward.set_text ( '1' )
  label_entry.pack_start ( gui_fields.num_align_forward, True, True, 0 )
  gui_fields.num_align_forward.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()

  '''
  button = gtk.Button("Abort")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", stop_callback, zpa_original )
  button.show()

  button = gtk.Button("+")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", add_panel_callback, zpa_original )
  button.show()

  button = gtk.Button("-")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", rem_panel_callback, zpa_original )
  button.show()
  '''

  # Show the main window
  window.show()

  # gtk.idle_add ( background_callback, zpa_original )

  # Turn control over to GTK to run everything from here onward.
  gtk.main()
  return 0

#######################################################################

def gtk_main():
  import sys
  if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
      try:
        s = int(arg)
        global_win_width = global_win_height = s
      except:
        pass
  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
  main_gtk_version()


def qt_main():

  # This provides default command line parameters if none are given (as with "Idle")
  if len(sys.argv) <= 2:
      sys.argv = [ __file__, "-f", "vj_097_1k1k_1.jpg" ]


  options = argparse.ArgumentParser()
  options.add_argument("-f", "--file", type=str, required=True)
  options.add_argument("-t", "--tiff", type=str, required=False)
  args = options.parse_args()
  print ( "Qt Mode: " + str(args) )
  fname = ''
  if 'file' in args:
    fname = args.file
  tname = ''
  if 'tiff' in args:
    if args.tiff != None:
      tname = args.tiff
      py_swift_tiff.dump_tiff ( tname )

  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

  # Qt Application
  app = QApplication(sys.argv)

  window = app_window.MainWindow(fname)
  # window.resize(pixmap.width(),pixmap.height())  # Optionally resize to image

  window.show()
  sys.exit(app.exec_())



if __name__ == '__main__':
  if gtk_mode:
    gtk_main()
  else:
    qt_main()

