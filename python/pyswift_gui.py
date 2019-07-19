# Things to fix:
#
#   Match points need to match the images they come from
#   Aligning should not clear the match points


#!/usr/bin/env python

#__import__('code').interact(local = locals())
import time
import os
import sys
import json
import math
import random
import shutil

import pygtk
pygtk.require('2.0')
import gobject
import gtk

import app_window

global image_hbox
image_hbox = None

global zpa_original
zpa_original = None

global panel_list
panel_list = []

global global_win_width
global global_win_height
global_win_width = 800
global_win_height = 800

global alignment_layer_list
alignment_layer_list = []
global alignment_layer_index
alignment_layer_index = -1

global project_file_name
project_file_name = ""

global project_path
project_path = None

global destination_path
destination_path = ""

global window
window = None

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

global debug_level
debug_level = 50

def print_debug ( level, str ):
  global debug_level
  if level < debug_level:
    print ( str )

''' Available Cursors - some with descriptions

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


    ["Cursor_ARROW", gtk.gdk.ARROW],
    ["Cursor_BASED_ARROW_DOWN", gtk.gdk.BASED_ARROW_DOWN],
    ["Cursor_BASED_ARROW_UP", gtk.gdk.BASED_ARROW_UP],
    ["Cursor_BOAT", gtk.gdk.BOAT],
    ["Cursor_BOGOSITY", gtk.gdk.BOGOSITY],
    ["Cursor_BOTTOM_LEFT_CORNER", gtk.gdk.BOTTOM_LEFT_CORNER],
    ["Cursor_BOTTOM_RIGHT_CORNER", gtk.gdk.BOTTOM_RIGHT_CORNER],
    ["Cursor_BOTTOM_SIDE", gtk.gdk.BOTTOM_SIDE],
    ["Cursor_BOTTOM_TEE", gtk.gdk.BOTTOM_TEE],
    ["Cursor_BOX_SPIRAL", gtk.gdk.BOX_SPIRAL],
    ["Cursor_CLOCK", gtk.gdk.CLOCK],
    ["Cursor_COFFEE_MUG", gtk.gdk.COFFEE_MUG],
    ["Cursor_DOUBLE_ARROW", gtk.gdk.DOUBLE_ARROW],
    ["Cursor_DRAFT_LARGE", gtk.gdk.DRAFT_LARGE],
    ["Cursor_DRAFT_SMALL", gtk.gdk.DRAFT_SMALL],
    ["Cursor_DRAPED_BOX", gtk.gdk.DRAPED_BOX],
    ["Cursor_EXCHANGE", gtk.gdk.EXCHANGE],
    ["Cursor_FLEUR", gtk.gdk.FLEUR],
    ["Cursor_GOBBLER", gtk.gdk.GOBBLER],
    ["Cursor_GUMBY", gtk.gdk.GUMBY],
    ["Cursor_HEART", gtk.gdk.HEART],
    ["Cursor_ICON", gtk.gdk.ICON],
    ["Cursor_LEFT_PTR", gtk.gdk.LEFT_PTR],
    ["Cursor_LEFT_SIDE", gtk.gdk.LEFT_SIDE],
    ["Cursor_LEFT_TEE", gtk.gdk.LEFT_TEE],
    ["Cursor_LEFTBUTTON", gtk.gdk.LEFTBUTTON],
    ["Cursor_LL_ANGLE", gtk.gdk.LL_ANGLE],
    ["Cursor_LR_ANGLE", gtk.gdk.LR_ANGLE],
    ["Cursor_MAN", gtk.gdk.MAN],
    ["Cursor_MIDDLEBUTTON", gtk.gdk.MIDDLEBUTTON],
    ["Cursor_MOUSE", gtk.gdk.MOUSE],
    ["Cursor_PENCIL", gtk.gdk.PENCIL],
    ["Cursor_PIRATE", gtk.gdk.PIRATE],
    ["Cursor_QUESTION_ARROW", gtk.gdk.QUESTION_ARROW],
    ["Cursor_RIGHT_PTR", gtk.gdk.RIGHT_PTR],
    ["Cursor_RIGHT_SIDE", gtk.gdk.RIGHT_SIDE],
    ["Cursor_RIGHT_TEE", gtk.gdk.RIGHT_TEE],
    ["Cursor_RIGHTBUTTON", gtk.gdk.RIGHTBUTTON],
    ["Cursor_RTL_LOGO", gtk.gdk.RTL_LOGO],
    ["Cursor_SAILBOAT", gtk.gdk.SAILBOAT],
    ["Cursor_SB_DOWN_ARROW", gtk.gdk.SB_DOWN_ARROW],
    ["Cursor_SB_H_DOUBLE_ARROW", gtk.gdk.SB_H_DOUBLE_ARROW],
    ["Cursor_SB_LEFT_ARROW", gtk.gdk.SB_LEFT_ARROW],
    ["Cursor_SB_RIGHT_ARROW", gtk.gdk.SB_RIGHT_ARROW],
    ["Cursor_SB_UP_ARROW", gtk.gdk.SB_UP_ARROW],
    ["Cursor_SB_V_DOUBLE_ARROW", gtk.gdk.SB_V_DOUBLE_ARROW],
    ["Cursor_SHUTTLE", gtk.gdk.SHUTTLE],
    ["Cursor_SIZING", gtk.gdk.SIZING],
    ["Cursor_SPIDER", gtk.gdk.SPIDER],
    ["Cursor_SPRAYCAN", gtk.gdk.SPRAYCAN],
    ["Cursor_TCROSS", gtk.gdk.TCROSS],
    ["Cursor_TOP_LEFT_ARROW", gtk.gdk.TOP_LEFT_ARROW],
    ["Cursor_TOP_LEFT_CORNER", gtk.gdk.TOP_LEFT_CORNER],
    ["Cursor_TOP_RIGHT_CORNER", gtk.gdk.TOP_RIGHT_CORNER],
    ["Cursor_TOP_SIDE", gtk.gdk.TOP_SIDE],
    ["Cursor_TOP_TEE", gtk.gdk.TOP_TEE],
    ["Cursor_TREK", gtk.gdk.TREK],
    ["Cursor_UL_ANGLE", gtk.gdk.UL_ANGLE],
    ["Cursor_UMBRELLA", gtk.gdk.UMBRELLA],
    ["Cursor_UR_ANGLE", gtk.gdk.UR_ANGLE],
    ["Cursor_WATCH", gtk.gdk.WATCH],   # Animated "waiting" cursor!!
    ["Cursor_XTERM", gtk.gdk.XTERM]
    # ["Cursor_CURSOR_IS_PIXMAP", gtk.gdk.CURSOR_IS_PIXMAP]  # This will crash!!
  ]
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
    self.bias_dx_entry = None
    self.bias_dy_entry = None


''' This variable gives global access to the GUI widgets '''
gui_fields = gui_fields_class()


class graphic_primitive:
  ''' This base class defines something that can be drawn '''
  def __init__ ( self ):
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
  def __init__ ( self, x, y, s, coordsys='i', color=[1.0,1.0,1.0], graphic_group="default" ):
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
    pgl.set_text ( self.s )
    drawable.draw_layout ( gc, x, y, pgl )

    # Restore the previous color
    gc.foreground = old_fg
    return False


class annotated_image:
  ''' An image with a series of drawing primitives defined in
      the pixel coordinates of the image. '''
  def __init__ ( self, file_name=None, clone_from=None, role=None ):
    # Initialize everything to defaults
    self.file_name = file_name
    self.image = None
    self.graphics_items = []
    self.role = role
    # self.results_dict = None

    # Copy in the clone if provided
    if type(clone_from) != type(None):
      self.file_name = clone_from.file_name
      self.image = clone_from.image
      self.graphics_items = [ gi for gi in clone_from.graphics_items ]

    # Over-ride other items as provided
    if type(file_name) != type(None):
      self.file_name = file_name
    if role != None:
      self.role = role
    if (type(self.image) == type(None)) and (type(self.file_name) != type(None)):
      try:
        self.image = gtk.gdk.pixbuf_new_from_file ( self.file_name )
        print_debug ( 50, "Loaded " + str(self.file_name) )
      except:
        print_debug ( -1, "Got an exception in annotated_image constructor reading annotated image " + str(self.file_name) )
        # exit(1)
        self.image = None
      if type(self.file_name) != type(None):
        self.graphics_items.append ( graphic_text(100, 2, self.file_name.split('/')[-1], coordsys='p', color=[1, 1, 1]) )

  def to_string ( self ):
    return ( "AnnoImage \"" + str(self.file_name) + "\" with annotations: " + str([gi.to_string() for gi in self.graphics_items]) )

  def use_image_from ( self, other_annotated_image ):
    self.file_name = other_annotated_image.file_name
    self.image = other_annotated_image.image
    if type(self.file_name) != type(None):
      self.graphics_items.append ( graphic_text(100, 2, self.file_name.split('/')[-1], coordsys='p', color=[1, 1, 1]) )

  def set_role ( self, role ):
    self.role = role

  def get_marker_points ( self ):
    point_list = []
    for item in self.graphics_items:
      if item.marker:
        point_list.append ( [item.x, item.y] )
    return point_list

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
    self.bias_dx = 0
    self.bias_dy = 0

    # This holds whatever is produced by this alignment
    self.results_dict = {}

    try:
      self.base_annotated_image = annotated_image ( self.base_image_name, role="base" )
      # By default, the first (and only) image in the list will be the base image
    except:
      self.base_annotated_image = annotated_image ( None, role="base" )

    # Always initialize with the image
    self.image_dict['base'] = self.base_annotated_image

  def to_string ( self ):
    s = "AlignLayer \"" + str(self.base_image_name) + "\" with images:"
    for k,v in self.image_dict.items():
      s = s + "\n  " + str(k) + ": " + v.to_string()
    return ( s )



# These two global functions are handy for callbacks

def store_fields_into_current_layer():
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
  a.bias_dx = float(gui_fields.bias_dx_entry.get_text())
  a.bias_dy = float(gui_fields.bias_dy_entry.get_text())


def store_current_layer_into_fields():
  a = alignment_layer_list[alignment_layer_index]
  # print_debug ( 50, " Index = " + str(alignment_layer_index) + ", base_name = " + a.base_image_name )
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
  gui_fields.bias_dx_entry.set_text(str(a.bias_dx))
  gui_fields.bias_dy_entry.set_text(str(a.bias_dy))


class zoom_panel ( app_window.zoom_pan_area ):
  '''zoom_panel - provide a drawing area that can be zoomed and panned.'''
  global gui_fields
  global panel_list

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
    if self.point_add_enabled:
      if point_mode and not point_delete_mode:
        global alignment_layer_list
        global alignment_layer_index
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
        global alignment_layer_list
        global alignment_layer_index
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
        # print ( "image has " + str(len(this_image.graphics_items)) + " items" )
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

    # print_debug ( 50, "Painting with len(alignment_layer_list) = " + str(len(alignment_layer_list)) )

    pix_buf = None
    if len(alignment_layer_list) > 0:
      # Draw one of the images
      if alignment_layer_index < len(alignment_layer_list):
        im_dict = alignment_layer_list[alignment_layer_index].image_dict
        if self.role in im_dict:
          pix_buf = im_dict[self.role].image

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
        alignment_layer_list[alignment_layer_index].image_dict['ref'] = annotated_image()
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

def run_alignment_callback ( align_all ):
  global alignment_layer_list
  global alignment_layer_index
  global destination_path
  global gui_fields
  global panel_list

  store_fields_into_current_layer()

  if len(destination_path) == 0:
    dest_err_dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK, message_format="Destination not set.")
    response = dest_err_dialog.run()
    dest_err_dialog.destroy()
    return

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
      alignment_layer_list[i].image_dict['aligned'] = annotated_image(None, role="aligned")

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
      print_debug ( 50, "Copying ( " + alignment_layer_list[i].base_image_name + " to " + os.path.join(destination_path,os.path.basename(alignment_layer_list[i].base_image_name)) + " )" )
      shutil.copyfile      ( alignment_layer_list[i].base_image_name,           os.path.join(destination_path,os.path.basename(alignment_layer_list[i].base_image_name)) )

      # Create a new identity transform for this layer even though it's not otherwise needed
      alignment_layer_list[j].align_proc = align_swiftir.alignment_process ( alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name, destination_path, layer_dict=layer_dict, cumulative_afm=None )

      alignment_layer_list[j].image_dict['ref'] = annotated_image(None, role="ref")
      #alignment_layer_list[j].image_dict['base'] = annotated_image(clone_from=alignment_layer_list[j].base_annotated_image, role="base")
      alignment_layer_list[j].image_dict['aligned'] = annotated_image(clone_from=alignment_layer_list[j].base_annotated_image, role="aligned")

      snr_value = sys.float_info.max

      alignment_layer_list[j].results_dict = {}
      alignment_layer_list[j].results_dict['snr'] = snr_value
      alignment_layer_list[j].results_dict['affine'] = [ [1, 0, 0], [0, 1, 0] ]
      alignment_layer_list[j].results_dict['cumulative_afm'] = [ [1, 0, 0], [0, 1, 0] ]

      alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 26, "SNR: inf", coordsys='p', color=[1, .5, .5]) )
      alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 46, "Affine: " + str2D(alignment_layer_list[j].results_dict['affine']), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )
      alignment_layer_list[j].image_dict['aligned'].graphics_items.append ( graphic_text(2, 66, "CumAff: " + str2D(alignment_layer_list[j].results_dict['cumulative_afm']), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )


    else:
      # Align the image at index j with the reference at index i

      if not 'cumulative_afm' in alignment_layer_list[i].results_dict:
        print_debug ( 1, "Cannot align from here (" + str(i) + " to " + str(j) + ") without a previous cumulative affine matrix." )
        return

      prev_afm = [ [ c for c in r ] for r in alignment_layer_list[i].results_dict['cumulative_afm'] ]  # Gets the cumulative from the stored values in previous layer

      print_debug ( 40, "Aligning: i=" + str(i) + " to j=" + str(j) )
      print_debug ( 50, "  Calling align_swiftir.align_images( " + alignment_layer_list[i].base_image_name + ", " + alignment_layer_list[j].base_image_name + ", " + destination_path + " )" )

      alignment_layer_list[j].align_proc = align_swiftir.alignment_process ( alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name, destination_path, layer_dict=layer_dict, cumulative_afm=prev_afm )
      alignment_layer_list[j].align_proc.align()
      recipe = alignment_layer_list[j].align_proc.recipe
      new_name = os.path.join ( destination_path, os.path.basename(alignment_layer_list[j].base_image_name) )

      # Put the proper images into the proper window slots

      print_debug ( 60, "Reading in new_name from " + str(new_name) )
      annotated_img = annotated_image(new_name, role="aligned")
      annotated_img.graphics_items.append ( graphic_text(2, 26, "SNR: %.4g" % (recipe.ingredients[-1].snr[0]), coordsys='p', color=[1, .5, .5]) )
      annotated_img.graphics_items.append ( graphic_text(2, 46, "Affine: " + str2D(recipe.afm), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )
      annotated_img.graphics_items.append ( graphic_text(2, 66, "CumAff: " + str2D(alignment_layer_list[j].align_proc.cumulative_afm), coordsys='p', color=[1, .5, .5],graphic_group="Affines") )

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
        if True or show_window_centers:
          # Draw dots in the center of each psta (could be pmov) with SNR for each
          for wi in range(s):
            annotated_img.graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
            annotated_img.graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )

            alignment_layer_list[j].image_dict['ref'].graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
            alignment_layer_list[j].image_dict['ref'].graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )

            alignment_layer_list[j].image_dict['base'].graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c,graphic_group="Centers") )
            alignment_layer_list[j].image_dict['base'].graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c,graphic_group="Centers") )
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


def menu_callback ( widget, data=None ):
  # Menu items will trigger this call
  # The menu items are set up to pass either a tuple:
  #  (command_string, zpa)
  # or a plain string:
  #  command_string
  # Checking the type() of data will determine which

  if type(data) == type((True,False)):
    # Any tuple passed is assumed to be: (command, zpa)
    command = data[0]
    zpa = data[1]

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

      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
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
      image_filter.add_pattern("*.[Gg][Ii][Ff]")
      file_chooser.add_filter(image_filter)
      image_filter=gtk.FileFilter()
      image_filter.set_name("All Files")
      image_filter.add_pattern("*")
      file_chooser.add_filter(image_filter)
      response = file_chooser.run()

      if response == gtk.RESPONSE_OK:
        i = 1
        file_name_list = file_chooser.get_filenames()
        print_debug ( 20, "Selected Files: " + str(file_name_list) )
        # alignment_layer_list = []
        for f in file_name_list:
          a = alignment_layer ( f )
          a.trans_ww = 256
          a.trans_addx = 256 + i
          a.trans_addy = 256 + i

          a.trans_ww = 10 + i
          a.trans_addx = 20 + i
          a.trans_addy = 30 + i

          a.skip = False

          a.affine_enabled = True
          a.affine_ww = 40 + i
          a.affine_addx = 50 + i
          a.affine_addy = 60 + i

          a.bias_enabled = True
          a.bias_dx = 70 + i
          a.bias_dy = 80 + i

          i += 1
          alignment_layer_list.append ( a )

      file_chooser.destroy()
      print_debug ( 90, "Done with dialog" )
      # Draw the windows
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
            a.image_dict["ref"] = annotated_image(clone_from=alignment_layer_list[layer_index-1].image_dict["base"],role="ref")
        # Create an empty aligned image as a place holder (to keep the panels from changing after alignment)
        #a.image_dict["aligned"] = annotated_image(None,role="aligned")
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

            proj_dict = json.loads ( text )
            print_debug ( 70, str(proj_dict) )
            print_debug ( 5, "Project file version " + str(proj_dict['version']) )
            if proj_dict['version'] < 0.05:
              print_debug ( -1, "Unable to read from versions before 0.1" )
              exit (99)
            if proj_dict['version'] > 0.15:
              print_debug ( -1, "Unable to read from versions above 0.1" )
              exit (99)
            print_debug ( 50, "Project file method " + str(proj_dict['method']) )
            if 'data' in proj_dict:
              if 'destination_path' in proj_dict['data']:
                destination_path = proj_dict['data']['destination_path']
                # Make the destination absolute
                if not os.path.isabs(destination_path):
                  destination_path = os.path.join ( project_path, destination_path )
                destination_path = os.path.realpath ( destination_path )
                gui_fields.dest_label.set_text ( "Destination: " + str(destination_path) )
              if 'alignment_stack' in proj_dict['data']:
                imagestack = proj_dict['data']['alignment_stack']
                if len(imagestack) > 0:
                  alignment_layer_index = 0
                  alignment_layer_list = []
                  for json_alignment_layer in imagestack:
                    if 'images' in json_alignment_layer:
                      im_list = json_alignment_layer['images']
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
                                a.image_dict["base"].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )

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
                                a.image_dict["ref"] = annotated_image(image_fname,role="ref")

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
                                      a.image_dict["ref"].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )

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
                                a.image_dict["aligned"] = annotated_image(image_fname,role="aligned")
                            if 'metadata' in aligned:
                              if 'annotations' in aligned['metadata']:
                                ann_list = aligned['metadata']['annotations']
                                for ann_item in ann_list:
                                  print_debug ( 60, "Aligned has " + str(ann_item) )
                                  a.image_dict["aligned"].graphics_items.append ( graphic_primitive().from_json ( ann_item ) )

                          alignment_layer_list.append ( a )


      file_chooser.destroy()
      print_debug ( 90, "Done with dialog" )
      # Copy the "base" images into the "ref" images for the next layer
      # This is SWiFT specific, but makes it simpler to use for now
      layer_index = 0
      for a in alignment_layer_list:
        if layer_index > 0:
          # Create a reference image from the previous layer if it wasn't read in via the JSON above
          if not 'ref' in a.image_dict:
            a.image_dict["ref"] = annotated_image(clone_from=alignment_layer_list[layer_index-1].image_dict["base"],role="ref")
        # Create an empty aligned image as a place holder (to keep the panels from changing after alignment)
        #a.image_dict["aligned"] = annotated_image(None,role="aligned")
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
        # Actually write the file
        gui_fields.proj_label.set_text ( "Project File: " + str(project_file_name) )
        rel_dest_path = ""
        if len(destination_path) > 0:
          rel_dest_path = os.path.relpath(destination_path,start=project_path)

        print_debug ( 50, "Saving destination path = " + str(destination_path) )
        f = open ( project_file_name, 'w' )
        f.write ( '{\n' )
        f.write ( '  "version": 0.1,\n' )
        f.write ( '  "method": "SWiFT-IR",\n' )
        f.write ( '  "data": {\n' )
        f.write ( '    "source_path": "",\n' )
        f.write ( '    "destination_path": "' + str(rel_dest_path) + '",\n' )
        f.write ( '    "pairwise_alignment": true,\n' )
        f.write ( '    "defaults": {\n' )
        f.write ( '      "align_to_next_pars": {\n' )
        f.write ( '        "window_size": 1024,\n' )
        f.write ( '        "addx": 800,\n' )
        f.write ( '        "addy": 800,\n' )
        f.write ( '        "output_level": 0\n' )
        f.write ( '      }\n' )
        f.write ( '    },\n' )

        if alignment_layer_list != None:
          if len(alignment_layer_list) > 0:
            f.write ( '    "alignment_stack": [\n' )
            for a in alignment_layer_list:
              f.write ( '      {\n' )
              f.write ( '        "skip": ' + str(a.skip).lower() + ',\n' )
              if a != alignment_layer_list[-1]:
                # Not sure what to leave out for last image ... keep all for now
                pass
              f.write ( '        "images": {\n' )

              img_keys = sorted(a.image_dict.keys(), reverse=True)
              for k in img_keys:
                im = a.image_dict[k]
                #print_debug ( 90, "    " + str(k) + " alignment points: " + str(im.get_marker_points()) )
                f.write ( '          "' + k + '": {\n' )  # "base": {
                # rel_file_name = os.path.relpath(a.base_image_name,start=project_path)
                print_debug ( 90, "Try to get relpath for " + str(im.file_name) + " starting at " + str(project_path) )
                rel_file_name = ""
                if type(im.file_name) != type(None):
                  rel_file_name = os.path.relpath(im.file_name,start=project_path)
                f.write ( '            "filename": "' + rel_file_name + '",\n' )
                f.write ( '            "metadata": {\n' )
                f.write ( '              "match_points": ' + str(im.get_marker_points()) + ',\n' )
                if len(im.graphics_items) <= 0:
                  f.write ( '              "annotations": []\n' )
                else:
                  f.write ( '              "annotations": [\n' )
                  # Filter out the markers which are handled in other code
                  non_marker_list = [ gi for gi in im.graphics_items if not gi.marker ]
                  # Only output the non-markers being careful not to add a trailing comma
                  for gi_index in range(len(non_marker_list)):
                    gi = non_marker_list[gi_index]
                    f.write ( "                " + gi.to_json_string() )
                    if gi_index < (len(non_marker_list)-1):
                      f.write ( ',\n' )
                    else:
                      f.write ( '\n' )
                  f.write ( '              ]\n' )
                f.write ( '            }\n' )
                if k != img_keys[-1]:
                  f.write ( '          },\n' )
                else:
                  f.write ( '          }\n' )
              f.write ( '        },\n' )
              f.write ( '        "align_to_ref_method": {\n' )
              f.write ( '          "selected_method": "' + str(a.align_method_text) + '",\n' )
              f.write ( '          "method_options": ["Auto Swim Align", "Match Point Align"],\n' )
              f.write ( '          "method_data": {\n' )
              f.write ( '            "window_size": ' + str(a.trans_ww) + ',\n' )
              f.write ( '            "addx": ' + str(a.trans_addx) + ',\n' )
              f.write ( '            "addy": ' + str(a.trans_addy) + ',\n' )
              f.write ( '            "output_level": 0\n' )
              f.write ( '          },\n' )
              f.write ( '          "method_results": {\n' )
              #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

              if type(a.results_dict) != type(None):
                if 'affine' in a.results_dict:
                  f.write ( '            "affine_matrix": ' + str(a.results_dict['affine']) + ',\n' )
                if 'cumulative_afm' in a.results_dict:
                  f.write ( '            "cumulative_afm": ' + str(a.results_dict['cumulative_afm']) + ',\n' )
                if 'snr' in a.results_dict:
                  f.write ( '            "snr": ' + str(a.results_dict['snr']) + '\n' )
              #f.write ( '            "snr": {\n' )
              #f.write ( '              "final": 1.234,\n' )
              #f.write ( '              "process": []\n' )
              #f.write ( '            }\n' )
              f.write ( '          }\n' )
              f.write ( '        }\n' )
              if a != alignment_layer_list[-1]:
                f.write ( '      },\n' )
              else:
                f.write ( '      }\n' )
            f.write ( '    ]\n' )
            f.write ( '  }\n' )
            f.write ( '}\n' )

      #global project_path
      #project_path = None

    elif command == "ClearAll":

      clear_all = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="Remove All Layers?")
      response = clear_all.run()
      if response == gtk.RESPONSE_OK:
        print_debug ( 20, "Clearing all layers..." )
        alignment_layer_index = 0
        alignment_layer_list = []
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
            #al.image_dict = {}
            #al.image_dict['base'] = al.base_annotated_image
            al.image_dict['aligned'] = annotated_image(None, role="aligned")
          zpa_original.queue_draw()
          for p in panel_list:
            p.queue_draw()
        clear_out.destroy()

    elif command == "LimZoom":

      zpa_original.max_zoom_count = 10
      zpa_original.min_zoom_count = -15

    elif command == "UnLimZoom":

      # This is now a toggle
      if zpa_original.max_zoom_count > 100:
        zpa_original.max_zoom_count = 10
        zpa_original.min_zoom_count = -15
      else:
        zpa_original.max_zoom_count = 1000
        zpa_original.min_zoom_count = -1500

    elif command == "Refresh":

      refresh_all_images()

    elif command == "ImCenter":

      print_debug ( 50, "Centering images" )
      center_all_images()

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

    elif command == "Structs":

      print_data_structures(panel_list, alignment_layer_list)

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
      print_debug ( 10, "New debug level is " + str(debug_level) )

    else:

      print_debug ( 20, "Menu option \"" + command + "\" is not handled yet." )

  return True



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
        print ("")


def refresh_all_images():
  # Determine how many panels are needed and create them as needed
  global panel_list
  max_extra_panels = 0
  for a in alignment_layer_list:
    if len(a.image_dict.keys()) > 0:
      max_extra_panels = max(max_extra_panels, len(a.image_dict.keys()))
  if max_extra_panels < 1:
    # Must always keep one window
    max_extra_panels = 1
  print_debug ( 50, "Max extra = " + str(max_extra_panels) )
  num_cur_extra_panels = len(panel_list)
  if num_cur_extra_panels > max_extra_panels:
    # Remove the difference:
    for i in range(num_cur_extra_panels - max_extra_panels):
      rem_panel_callback ( zpa_original )
  elif num_cur_extra_panels < max_extra_panels:
    # Add the difference
    for i in range(max_extra_panels - num_cur_extra_panels):
      add_panel_callback ( zpa_original )


# Create the window and connect the events
def main():

  global gui_fields
  global window
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
    zpa_original.add_menu_item ( this_menu, menu_callback, "Clear All Images",  ("ClearAll", zpa_original ) )

  # Create a "Points" menu
  (points_menu, points_item) = zpa_original.add_menu ( "_Points" )
  if True: # An easy way to indent and still be legal Python
    this_menu = points_menu
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Alignment Point Mode",   ("PtMode", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Delete Points",   ("PtDel", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Clear All Alignment Points",   ("PtClear", zpa_original ) )

  # Create a "Set" menu
  (set_menu, set_item) = zpa_original.add_menu ( "_Set" )
  if True: # An easy way to indent and still be legal Python
    this_menu = set_menu
    # zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Limited Zoom",   ("LimZoom", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "UnLimited Zoom",   ("UnLimZoom", zpa_original ) )

    zpa_original.add_menu_sep  ( this_menu )
    # Create a "Set/Cursor" submenu
    # This didn't work ...
    #  (cursor_menu, set_item) = this_menu.add_menu_item ( "_Cursor" )
    #  if True: # An easy way to indent and still be legal Python
    # So put in the main menu for now:
    # Add cursors from the "cursor_options" array
    cursor_index = 0
    for cursor_pair in cursor_options:
      cursor_option_string = cursor_pair[0]
      zpa_original.add_menu_item ( this_menu, menu_callback, cursor_option_string[len('Cursor_'):],   (cursor_option_string, zpa_original ) )
      if cursor_index in cursor_option_seps:
        zpa_original.add_menu_sep  ( this_menu )
      cursor_index += 1

  # Create a "Debug" menu
  (debug_menu, debug_item) = zpa_original.add_menu ( "_Debug" )
  if True: # An easy way to indent and still be legal Python
    this_menu = debug_menu
    zpa_original.add_menu_item ( this_menu, menu_callback, "Python Console",   ("Debug", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Print Affine",   ("Affine", zpa_original ) )
    zpa_original.add_menu_item ( this_menu, menu_callback, "Print Structures",   ("Structs", zpa_original ) )
    zpa_original.add_menu_sep  ( this_menu )
    for level in [ 10*x for x in range(0,11) ]:
      zpa_original.add_menu_item ( this_menu, menu_callback, "Level " + str(level),   ("Level " + str(level), zpa_original ) )

  # Create a "Show" menu
  (show_menu, show_item) = zpa_original.add_menu ( "_Show" )
  if True: # An easy way to indent and still be legal Python
    this_menu = show_menu
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Window Centers",   ("WinCtrs", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Affines",   ("Affines", zpa_original ) )
    zpa_original.add_checkmenu_item ( this_menu, menu_callback, "Skipped Images",   ("ShowSkipped", zpa_original ), default=True )

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
  store.append ( ["Auto Swim Align"] )
  store.append ( ["Match Point Align"] )
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

  a_label = gtk.Label(" ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  gui_fields.bias_check_box = gtk.CheckButton("  Bias Pass:")
  controls_hbox.pack_start ( gui_fields.bias_check_box, True, True, 0 )
  gui_fields.bias_check_box.show()


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


if __name__ == '__main__':
  import sys
  if len(sys.argv) > 1:
    for arg in sys.argv[1:]:
      try:
        s = int(arg)
        global_win_width = global_win_height = s
      except:
        pass
  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
  main()
