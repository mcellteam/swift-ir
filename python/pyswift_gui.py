#!/usr/bin/env python

#__import__('code').interact(local = locals())
import time
import os
import json
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

global extra_windows_list
extra_windows_list = []

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

global show_spots
show_spots = False

global point_mode
point_mode = False

class gui_fields_class:
  ''' This class holds GUI widgets and not the persistent data. '''
  def __init__(self):
    self.proj_label = None
    self.dest_label = None
    self.trans_ww_entry = None
    self.trans_addx_entry = None
    self.trans_addy_entry = None
    self.skip_check_box = None
    self.affine_check_box = None
    self.affine_ww_entry = None
    self.affine_addx_entry = None
    self.affine_addy_entry = None
    self.bias_check_box = None
    self.bias_dx_entry = None
    self.bias_dy_entry = None
    self.num_align_forward = None

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


class graphic_line (graphic_primitive):
  def __init__ ( self, x1, y1, x2, y2, coordsys='i', color=[1.0,1.0,1.0] ):
    self.marker = False
    self.x1 = x1
    self.y1 = y1
    self.x2 = x2
    self.y2 = y2
    self.coordsys = coordsys
    self.color = color
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
  def __init__ ( self, x, y, dx, dy, coordsys='i', color=[1.0,1.0,1.0] ):
    self.marker = False
    self.x = x
    self.y = y
    self.dx = dx
    self.dy = dy
    self.coordsys = coordsys
    self.color = color
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
  def __init__ ( self, x, y, r, coordsys='i', color=[1.0,1.0,1.0], index=-1 ):
    self.marker = True
    self.x = x
    self.y = y
    self.r = r
    self.coordsys = coordsys
    self.color = color
    self.index = index
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
  def __init__ ( self, x, y, r, coordsys='i', color=[1.0,1.0,1.0] ):
    self.marker = False
    self.x = x
    self.y = y
    self.r = r
    self.coordsys = coordsys
    self.color = color
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
  def __init__ ( self, x, y, s, coordsys='i', color=[1.0,1.0,1.0] ):
    self.marker = False
    self.x = x
    self.y = y
    self.s = s
    self.coordsys = coordsys
    self.color = color
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
  def __init__ ( self, file_name=None ):
    self.file_name = file_name
    self.graphics_items = []
    self.image = None
    if type(self.file_name) != type(None):
      try:
        self.image = gtk.gdk.pixbuf_new_from_file ( self.file_name )
        print ( "Loaded " + str(self.file_name) )
      except:
        print ( "Got an exception in annotated_image constructor reading annotated image " + str(self.file_name) )
        # exit(1)
        self.image = None
      if type(self.file_name) != type(None):
        self.graphics_items.append ( graphic_text(10, 12, self.file_name.split('/')[-1], coordsys='p', color=[1, 1, 1]) )
        # self.graphics_items.append ( graphic_text(10, 42, "SNR:"+str(100*random.random()), coordsys='p', color=[1, .5, .5]) )

  def add_graphic ( self, item ):
    self.graphics_items.append ( item )



class alignment_layer:
  ''' An alignment_layer has a base image and a set of images and processes representing the relationships to its neighbors '''
  def __init__ ( self, base=None ):
    print ( "Constructing new alignment_layer with base " + str(base) )
    self.base_image_name = base
    self.align_proc = None

    # This holds a single annotated image
    self.base_annotated_image = None

    # This holds a list of annotated images to be stored and/or displayed.
    # The base image may be placed in this list as desired.
    self.image_list = []

    # These are the parameters used for this layer
    self.trans_ww = 256
    self.trans_addx = 256
    self.trans_addy = 256

    self.skip = False

    self.affine_enabled = True
    self.affine_ww = 256
    self.affine_addx = 256
    self.affine_addy = 256

    self.bias_enabled = True
    self.bias_dx = 0
    self.bias_dy = 0

    try:
      self.base_annotated_image = annotated_image ( self.base_image_name )
      # By default, the first (and only) image in the list will be the base image
    except:
      self.base_annotated_image = annotated_image ( None )

    # Always initialize with the image (whether actual or None)
    self.image_list.append ( self.base_annotated_image )


# These two global functions are handy for callbacks

def store_fields_into_current_layer():
  a = alignment_layer_list[alignment_layer_index]
  a.trans_ww = int(gui_fields.trans_ww_entry.get_text())
  a.trans_addx = int(gui_fields.trans_addx_entry.get_text())
  a.trans_addy = int(gui_fields.trans_addy_entry.get_text())
  a.skip = gui_fields.skip_check_box.get_active()
  a.affine_enabled = gui_fields.affine_check_box.get_active()
  a.affine_ww = int(gui_fields.affine_ww_entry.get_text())

  a.affine_addx = int(gui_fields.affine_addx_entry.get_text())
  a.affine_addy = int(gui_fields.affine_addy_entry.get_text())
  a.bias_enabled = gui_fields.bias_check_box.get_active()
  a.bias_dx = float(gui_fields.bias_dx_entry.get_text())
  a.bias_dy = float(gui_fields.bias_dy_entry.get_text())

def store_current_layer_into_fields():
  a = alignment_layer_list[alignment_layer_index]
  # print ( " Index = " + str(alignment_layer_index) + ", base_name = " + a.base_image_name )
  print ( " Index = " + str(alignment_layer_index) + ", base_name_ann = " + a.base_annotated_image.file_name )
  print ( "  trans_ww = " + str(a.trans_ww) + ", trans_addx = " + str(a.trans_addx) + ", trans_addy = " + str(a.trans_addy) )
  gui_fields.trans_ww_entry.set_text ( str(a.trans_ww) )
  gui_fields.trans_addx_entry.set_text ( str(a.trans_addx) )
  gui_fields.trans_addy_entry.set_text ( str(a.trans_addy) )
  gui_fields.skip_check_box.set_active ( a.skip )
  gui_fields.affine_check_box.set_active ( a.affine_enabled )
  gui_fields.affine_ww_entry.set_text ( str(a.affine_ww) )

  gui_fields.affine_addx_entry.set_text(str(a.affine_addx))
  gui_fields.affine_addy_entry.set_text(str(a.affine_addy))
  gui_fields.bias_check_box.set_active(a.bias_enabled)
  gui_fields.bias_dx_entry.set_text(str(a.bias_dx))
  gui_fields.bias_dy_entry.set_text(str(a.bias_dy))



class zoom_window ( app_window.zoom_pan_area ):
  '''zoom_window - provide a drawing area that can be zoomed and panned.'''
  global gui_fields

  def __init__ ( self, window, win_width, win_height, name="" ):
    # The "window_index" is intended to assign one of the layer's images to this window.
    # When window_index is >= 0, it will be an index into the "image_list" in each layer:
    #   alignment_layer_list[alignment_layer_index].image_list[window_index]
    # When the window_index is -1, that indicates that no image is to be drawn.
    # This provides a simple and dynamic way to assign images to zoom windows.
    # By default, new zoom windows will show the original image with 0.

    self.window_index = 0

    # Call the constructor for the parent app_window.zoom_pan_area:
    app_window.zoom_pan_area.__init__ ( self, window, win_width, win_height, name )

    # Connect the scroll event for the drawing area (from zoom_pan_area) to a local function:
    self.drawing_area.connect ( "scroll_event", self.mouse_scroll_callback, self )
    #self.drawing_area.connect ( "button_press_event", self.button_press_callback, self )

    # Create a "pango_layout" which seems to be needed for drawing text
    self.pangolayout = window.create_pango_layout("")
    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

  def button_press_callback ( self, canvas, event, zpa ):
    if point_mode:
      global alignment_layer_list
      global alignment_layer_index
      print ( "Got a button press in point mode at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
      print ( "  Image coordinates: " + str(self.x(event.x)) + "," + str(self.y(event.y)) )
      #if self == zpa_original:
      #  # Add a point to the original
      #  print ( "Adding a marker point to the original image" )
      #  alignment_layer_list[alignment_layer_index].base_annotated_image.graphics_items.append ( graphic_marker(self.x(event.x),self.y(event.y),6,'i',[1, 0, 0]) )
      if len(extra_windows_list) > 1:
        if self == extra_windows_list[0]['win']:
          # Add a point to the first
          print ( "Adding a marker point to the align image" )
          alignment_layer_list[alignment_layer_index].image_list[0].graphics_items.append ( graphic_marker(self.x(event.x),self.y(event.y),6,'i',[1, 0, 0],index=0) )
        if self == extra_windows_list[1]['win']:
          # Add a point to the second
          print ( "Adding a marker point to the align image" )
          alignment_layer_list[alignment_layer_index].image_list[1].graphics_items.append ( graphic_marker(self.x(event.x),self.y(event.y),6,'i',[1, 0, 0],index=1) )
      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      '''
      for w in extra_windows_list:
        w['win'].set_cursor ( cursor )
        w['drawing_area'].queue_draw()'''

    # print ( "pyswift_gui: A mouse button was pressed at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
    if 'GDK_SHIFT_MASK' in event.get_state().value_names:
      # Do any special processing for shift click
      # Print the mouse location in screen coordinates:
      print ( "pyswift_gui: A mouse button was pressed at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
      # Print the mouse location in image coordinates:
      print ( "pyswift_gui:   Image coordinates: " + str(self.x(event.x)) + "," + str(self.y(event.y)) )
      # return ( app_window.zoom_pan_area.button_press_callback ( self, canvas, event, zpa ) )
      return True # Event has been handled
    else:
      # Call the parent's function to handle the click
      return ( app_window.zoom_pan_area.button_press_callback ( self, canvas, event, zpa ) )
    return True  # Event has been handled, do not propagate further

  def button_release_callback ( self, canvas, event, zpa ):
    #print ( "A mouse button was released at x = " + str(event.x) + ", y = " + str(event.y) + "  state = " + str(event.state) )
    return ( app_window.zoom_pan_area.button_release_callback ( self, canvas, event, zpa ) )

  def mouse_scroll_callback ( self, canvas, event, zpa ):
    ''' Overload the base mouse_scroll_callback to provide custom UNshifted action. '''
    global extra_windows_list
    if 'GDK_SHIFT_MASK' in event.get_state().value_names:
      # Use shifted scroll wheel to zoom the image size
      return ( app_window.zoom_pan_area.mouse_scroll_callback ( self, canvas, event, zpa ) )
    else:
      # Use normal (unshifted) scroll wheel to move through the stack
      global alignment_layer_list
      global alignment_layer_index
      print ( "Moving through the stack with alignment_layer_index = " + str(alignment_layer_index) )
      if len(alignment_layer_list) <= 0:
        alignment_layer_index = -1
        print ( " Index = " + str(alignment_layer_index) )
      else:
        # Store the alignment_layer parameters into the image layer being exited
        store_fields_into_current_layer()
        # Move to the next image layer (potentially)
        if event.direction == gtk.gdk.SCROLL_UP:
          alignment_layer_index += 1
          if alignment_layer_index >= len(alignment_layer_list):
            alignment_layer_index =  len(alignment_layer_list)-1
        elif event.direction == gtk.gdk.SCROLL_DOWN:
          alignment_layer_index += -1
          if alignment_layer_index < 0:
            alignment_layer_index = 0

        # Display the alignment_layer parameters from the new section being viewed
        store_current_layer_into_fields()

        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      # Draw the windows
      zpa_original.queue_draw()
      for win_and_area in extra_windows_list:
        win_and_area['win'].queue_draw()
      return True

  def mouse_motion_callback ( self, canvas, event, zpa ):
    ''' Overload the base mouse_motion_callback when shifted '''
    if 'GDK_SHIFT_MASK' in event.get_state().value_names:
      # Ignore the event
      return False
    else:
      # Call the parent's function to handle the motion
      return ( app_window.zoom_pan_area.mouse_motion_callback ( self, canvas, event, zpa ) )

  def expose_callback ( self, drawing_area, event, zpa ):
    ''' Draw all the elements in this window '''
    display_time_index = zpa.user_data['display_time_index']
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
    # Draw the current state referenced by display_time_index
    t = 0

    global alignment_layer_list
    global alignment_layer_index

    # print ( "Painting with len(alignment_layer_list) = " + str(len(alignment_layer_list)) )

    pix_buf = None
    if len(alignment_layer_list) > 0:
      if self.window_index < 0:
        # Draw nothing
        pix_buf = None
      else:
        # Draw one of the images
        if alignment_layer_index < len(alignment_layer_list):
          im_list = alignment_layer_list[alignment_layer_index].image_list
          if self.window_index < len(im_list):
            pix_buf = im_list[self.window_index].image

    #if zpa.user_data['image_frame']:
    #  pix_buf = zpa.user_data['image_frame']

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
          print ( "Scaling with " + str(int(pbw*scale_w)) + " " + str(int(pbh*scale_h)) )
          scaled_image = pix_buf.scale_simple( int(pbw*scale_w), int(pbh*scale_h), gtk.gdk.INTERP_NEAREST )
          drawable.draw_pixbuf ( gc, scaled_image, 0, 0, zpa.wxi(0), zpa.wyi(0), -1, -1, gtk.gdk.RGB_DITHER_NONE )
      except:
        pass

    # Draw any annotations in the list
    if len(alignment_layer_list) > 0:
      if self.window_index < 0:
        # Draw nothing
        pass
      else:
        # Draw annotations
        if alignment_layer_index < len(alignment_layer_list):
          im_list = alignment_layer_list[alignment_layer_index].image_list
          if self.window_index < len(im_list):
            image_to_draw = im_list[self.window_index]
            color_index = 0
            for graphics_item in image_to_draw.graphics_items:
              if graphics_item.marker:
                print ( "Drawing a marker with index " + str(graphics_item.index) + ", in window " + str(self.window_index) )
                if graphics_item.index == self.window_index:
                  # Only draw when they match
                  color_index += 1
                  graphics_item.set_color_from_index ( color_index )
              else:
                graphics_item.draw ( zpa, drawing_area, self.pangolayout )

    # Draw a separator between the panes
    gc.foreground = colormap.alloc_color(32767,32767,32767)
    drawable.draw_line ( gc, 0, 0, 0, height )
    drawable.draw_line ( gc, width-1, 0, width-1, height )

    # Restore the previous color
    gc.foreground = old_fg
    return False


def set_all_or_fwd_callback ( set_all ):
  if set_all:
    print ( "Setting All ..." )
  else:
    print ( "Setting Forward ..." )
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
          # print ( "Copying " + str(a) )
          a.trans_ww = template.trans_ww
          a.trans_addx = template.trans_addx
          a.trans_addy = template.trans_addy
          # a.skip = template.skip
          a.affine_enabled = template.affine_enabled
          a.affine_ww = template.affine_ww
          a.affine_addx = template.affine_addx
          a.affine_addy = template.affine_addy
          a.bias_enabled = template.bias_enabled
          a.bias_dx = template.bias_dx
          a.bias_dy = template.bias_dy

  return True


def step_callback(zpa):
  display_time_index = zpa.user_data['display_time_index']
  zpa.get_drawing_area().queue_draw()
  return True


def step_in_callback(zpa):
  zpa.get_drawing_area().queue_draw()
  return True


def background_callback ( zpa ):
  if zpa.user_data['running']:
    t = time.time()
    if t - zpa.user_data['last_update'] > zpa.user_data['frame_delay']:
      #zpa.user_data['last_update'] = t
      #step_callback(zpa)
      print ( "  Running at time = " + str(t) )
      #zpa.queue_draw()
  return True


def add_window_callback ( zpa ):
  print ( "Add a Window" )
  global image_hbox
  global extra_windows_list
  global window

  new_win = zoom_window(window,global_win_width,global_win_height,"Python GTK version of SWiFT-GUI")
  new_win.window_index = len(extra_windows_list)

  new_win.user_data = {
                    'image_frame'        : None,
                    'image_frames'       : [],
                    'frame_number'       : -1,
                    'display_time_index' : -1,
                    'running'            : False,
                    'last_update'        : -1,
                    'show_legend'        : True,
                    'frame_delay'        : 0.1,
                    'size'               : 1.0
                  }

  # Set the relationships between "user" coordinates and "screen" coordinates

  new_win.set_x_scale ( 0.0, 300, 100.0, 400 )
  new_win.set_y_scale ( 0.0, 250 ,100.0, 350 )

  # The zoom/pan area has its own drawing area (that it zooms and pans)
  new_win_drawing_area = new_win.get_drawing_area()

  # Add the zoom/pan area to the vertical box (becomes the main area)
  image_hbox.pack_start(new_win_drawing_area, True, True, 0)

  new_win_drawing_area.show()

  # The zoom/pan area doesn't draw anything, so add our custom expose callback
  new_win_drawing_area.connect ( "expose_event", new_win.expose_callback, new_win )

  # Set the events that the zoom/pan area must respond to
  #  Note that zooming and panning requires button press and pointer motion
  #  Other events can be set and handled by user code as well
  new_win_drawing_area.set_events ( gtk.gdk.EXPOSURE_MASK
                                   | gtk.gdk.LEAVE_NOTIFY_MASK
                                   | gtk.gdk.BUTTON_PRESS_MASK
                                   | gtk.gdk.POINTER_MOTION_MASK
                                   | gtk.gdk.POINTER_MOTION_HINT_MASK )

  win_and_area = { "win":new_win, "drawing_area":new_win_drawing_area }
  extra_windows_list.append ( win_and_area )

  return True


def rem_window_callback ( zpa ):
  print ( "Remove a Window" )
  global image_hbox
  global extra_windows_list
  global window

  if len(extra_windows_list) > 1:
    image_hbox.remove(extra_windows_list[-1]['drawing_area'])
    extra_windows_list.pop(-1)
    return True

  return False


# import pyswim
import thread

import align_swiftir

def run_alignment_callback ( align_all ):
  global alignment_layer_list
  global alignment_layer_index
  global destination_path
  global gui_fields

  store_fields_into_current_layer()

  if len(destination_path) == 0:
    dest_err_dialog = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK, message_format="Destination not set.")
    response = dest_err_dialog.run()
    dest_err_dialog.destroy()
    return

  # Do it the new way
  align_pairs = []  # List of images to align with each other, a repeated index means copy directly to the output (a "golden section")
  last_ref = -1
  for i in range(len(alignment_layer_list)):
    if alignment_layer_list[i].skip == False:
      if last_ref < 0:
        # This image was not skipped, but their is no previous, so just copy to itself
        align_pairs.append ( [i, i] )
      else:
        # There was a previously unskipped image and this image is unskipped
        # Therefore, add this pair to the list
        align_pairs.append ( [last_ref, i] )
      # This unskipped image will always become the last unskipped
      last_ref = i
    else:
      # Clear out the aligned images, but preserve the other images
      old_list = alignment_layer_list[i].image_list
      alignment_layer_list[i].image_list = []
      if len(old_list) > 0:
        alignment_layer_list[i].image_list.append ( old_list[0] )
        if len(old_list) > 1:
          alignment_layer_list[i].image_list.append ( old_list[1] )

  print ( "Full list after removing skips:" )
  for apair in align_pairs:
    print ( "  Alignment pair: " + str(apair) )

  if not align_all:
    # Retain only those pairs that start after this index
    if alignment_layer_index == 0:
      # Include the current layer to make the original copy again
      new_pairs = [ p for p in align_pairs if p[1] >= alignment_layer_index ]
    else:
      # Exclude the current layer
      new_pairs = [ p for p in align_pairs if p[1] > alignment_layer_index ]
    align_pairs = new_pairs
    # Remove any pairs beyond the number forward
    num_forward_str = gui_fields.num_align_forward.get_text()
    if len(num_forward_str.strip()) > 0:
      # A forward limit has been entered
      try:
        num_forward = int(num_forward_str.strip())
        new_pairs = [ p for p in align_pairs if p[1] <= alignment_layer_index+num_forward ]
        align_pairs = new_pairs
      except:
        print ( "The number forward should be an integer and not " + num_forward_str )

  print ( "Full list after removing start and forward limits:" )
  for apair in align_pairs:
    print ( "  Alignment pair: " + str(apair) )

  for apair in align_pairs:
    i = apair[0]
    j = apair[1]
    print ( "===============================================================================" )
    print ( "Aligning " + str(i) + " to " + str(j) + " with:" )
    print ( "" )
    print ( "  base                     = " + str(alignment_layer_list[i].base_image_name) )
    print ( "  adjust                   = " + str(alignment_layer_list[j].base_image_name) )
    print ( "  skip                     = " + str(alignment_layer_list[i].skip) )
    print ( "" )
    print ( "  translation window width = " + str(alignment_layer_list[i].trans_ww) )
    print ( "  translation addx         = " + str(alignment_layer_list[i].trans_addx) )
    print ( "  translation addy         = " + str(alignment_layer_list[i].trans_addy) )
    print ( "" )
    print ( "  affine enabled           = " + str(alignment_layer_list[i].affine_enabled) )
    print ( "  affine window width      = " + str(alignment_layer_list[i].affine_ww) )
    print ( "  affine addx              = " + str(alignment_layer_list[i].affine_addx) )
    print ( "  affine addy              = " + str(alignment_layer_list[i].affine_addy) )
    print ( "" )
    print ( "  bias enabled             = " + str(alignment_layer_list[i].bias_enabled) )
    print ( "  bias dx                  = " + str(alignment_layer_list[i].bias_dx) )
    print ( "  bias dy                  = " + str(alignment_layer_list[i].bias_dy) )

  # Perform the actual alignment
  for apair in align_pairs:
    i = apair[0] # Reference
    j = apair[1] # Current moving
    print ( "Clearing image list for layer " + str(j) )
    alignment_layer_list[j].image_list = []

    annotated_img = None
    if i == j:
      # This case (i==j) means make a copy of the original in the destination location
      print ( "Copying ( " + alignment_layer_list[i].base_image_name + " to " + os.path.join(destination_path,os.path.basename(alignment_layer_list[i].base_image_name)) + " )" )
      shutil.copyfile      ( alignment_layer_list[i].base_image_name,           os.path.join(destination_path,os.path.basename(alignment_layer_list[i].base_image_name)) )

      # Create a new identity transform for this layer even though it's not otherwise needed
      alignment_layer_list[i].align_proc = align_swiftir.alignment_process ( alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name, destination_path, None )

      # Put the proper images into the proper window slots
      alignment_layer_list[j].image_list.append ( annotated_image(None) )
      alignment_layer_list[j].image_list.append ( alignment_layer_list[j].base_annotated_image )
      alignment_layer_list[j].image_list.append ( alignment_layer_list[j].base_annotated_image )

    else:
      # Align the image at index j with the reference at index i
      print (    "Calling align_swiftir.align_images( " + alignment_layer_list[i].base_image_name + ", " + alignment_layer_list[j].base_image_name + ", " + destination_path + " )" )
      prev_afm = alignment_layer_list[i].align_proc.cumulative_afm
      alignment_layer_list[j].align_proc = align_swiftir.alignment_process ( alignment_layer_list[i].base_image_name, alignment_layer_list[j].base_image_name, destination_path, prev_afm )
      alignment_layer_list[j].align_proc.align()
      recipe = alignment_layer_list[j].align_proc.recipe
      new_name = os.path.join ( destination_path, os.path.basename(alignment_layer_list[j].base_image_name) )

      # Put the proper images into the proper window slots
      alignment_layer_list[j].image_list.append ( alignment_layer_list[i].base_annotated_image )
      alignment_layer_list[j].image_list.append ( alignment_layer_list[j].base_annotated_image )

      print ( "Reading in new_name from " + str(new_name) )
      annotated_img = annotated_image(new_name)
      annotated_img.graphics_items.append ( graphic_text(10, 42, "SNR:"+str(recipe.recipe[-1].snr[0]), coordsys='p', color=[1, .5, .5]) )

      for ri in range(len(recipe.recipe)):
        # Make a color for this recipe item
        c = [(ri+1)%2,((ri+1)/2)%2,((ri+1)/4)%2]
        r = recipe.recipe[ri]
        s = len(r.psta[0])
        ww = r.ww
        if type(ww) == type(1):
          # ww is an integer, so turn it into an nxn tuple
          ww = (ww,ww)
        global show_spots
        if show_spots:
          # Draw dots in the center of each psta (could be pmov) with SNR for each
          for wi in range(s):
            annotated_img.graphics_items.append ( graphic_dot(r.psta[0][wi],r.psta[1][wi],6,'i',color=c) )
            annotated_img.graphics_items.append ( graphic_text(r.psta[0][wi]+4,r.psta[1][wi],'%.1f'%r.snr[wi],'i',color=c) )
        print ( "  Recipe " + str(ri) + " has " + str(s) + " " + str(ww[0]) + "x" + str(ww[1]) + " windows" )

      alignment_layer_list[j].image_list.append ( annotated_img )

      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})



  # The following work manually, but gave error when done here
  # The try/excepts didn't help
  print ( "Try refreshing" )
  try:
    refresh_all_images()
  except:
    pass
  print ( "Try centering" )
  try:
    center_all_images()
  except:
    pass
  print ( "Try refreshing again" )
  try:
    refresh_all_images()
  except:
    pass
  print ( "Try centering again" )
  try:
    center_all_images()
  except:
    pass



def run_callback ( zpa ):
  # print ( "Run " )
  # zpa.user_data['running'] = True
  print ( "Starting a thread" )
  try:
    # thread.start_new_thread ( pyswim.do_alignment, ("data",5,) )
    pass
  except:
    print ( "Unable to start thread" )
  print ( "Done starting a thread" )
  return True

def stop_callback ( zpa ):
  # print ( "Stop " )
  zpa.user_data['running'] = False
  return True




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
    global extra_windows_list

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
          print ( "  Layer " + str(i) + ": Alignment is None" )
        else:
          if type(alignment_layer_list[i].align_proc) == type(None):
            print ( "  Layer " + str(i) + ": Alignment Process is None" )
          else:
            affine = alignment_layer_list[i].align_proc.cumulative_afm
            print ( "  Layer " + str(i) + ": Affine is " + str(affine) )

    elif command == "Debug":
      print ( "Handy global items:" )
      print ( "  project_path" )
      print ( "  project_file_name" )
      print ( "  destination_path" )
      print ( "  zpa_original" )
      print ( "  alignment_layer_list" )
      print ( "  alignment_layer_index" )
      print ( "  extra_windows_list" )
      print ( "  show_spots" )
      print ( "  point_mode" )
      print ( "Handy local items:" )
      print ( "  widget" )
      print ( "  data" )
      print ( "  command" )
      print ( "  zpa" )

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
        print ( "Selected Directory: " + str(destination_path) )

        gui_fields.dest_label.set_text ( "Destination: " + str(destination_path) )

      file_chooser.destroy()
      print ( "Done with dialog" )
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
        print ( "Selected Files: " + str(file_name_list) )
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
      print ( "Done with dialog" )
      # Draw the windows
      zpa_original.queue_draw()


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
            print ( str(proj_dict) )
            print ( "Project file version " + str(proj_dict['version']) )
            print ( "Project file method " + str(proj_dict['method']) )
            if 'data' in proj_dict:
              if 'destination_path' in proj_dict['data']:
                destination_path = proj_dict['data']['destination_path']
                # Make the destination absolute
                if not os.path.isabs(destination_path):
                  destination_path = os.path.join ( project_path, destination_path )
                destination_path = os.path.realpath ( destination_path )
                gui_fields.dest_label.set_text ( "Destination: " + str(destination_path) )
              if 'imagestack' in proj_dict['data']:
                imagestack = proj_dict['data']['imagestack']
                if len(imagestack) > 0:
                  alignment_layer_index = 0
                  alignment_layer_list = []
                  for json_alignment_layer in imagestack:
                    image_fname = json_alignment_layer['filename']
                    # Convert to absolute as needed
                    if not os.path.isabs(image_fname):
                      image_fname = os.path.join ( project_path, image_fname )
                    image_fname = os.path.realpath ( image_fname )
                    a = alignment_layer ( image_fname )
                    if 'skip' in json_alignment_layer:
                      a.skip = json_alignment_layer['skip']
                    if 'align_to_next_pars' in json_alignment_layer:
                      pars = json_alignment_layer['align_to_next_pars']
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
                    alignment_layer_list.append ( a )
      file_chooser.destroy()
      print ( "Done with dialog" )
      refresh_all_images()
      center_all_images()
      zpa_original.queue_draw()

    elif (command == "SaveProj") or (command == "SaveProjAs"):

      print ( "Save with: project_path = " + str(project_path) )
      print ( "Save with: project_file_name = " + str(project_file_name) )
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
        print ( "Done with dialog" )

      if len(project_file_name) > 0:
        # Actually write the file
        gui_fields.proj_label.set_text ( "Project File: " + str(project_file_name) )
        rel_dest_path = ""
        if len(destination_path) > 0:
          rel_dest_path = os.path.relpath(destination_path,start=project_path)

        print ( "Saving destination path = " + str(destination_path) )
        f = open ( project_file_name, 'w' )
        f.write ( '{\n' )
        f.write ( '  "version": 0.0,\n' )
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
            f.write ( '    "imagestack": [\n' )
            for a in alignment_layer_list:
              f.write ( '      {\n' )
              f.write ( '        "skip": ' + str(a.skip).lower() + ',\n' )
              rel_file_name = os.path.relpath(a.base_image_name,start=project_path)
              if a != alignment_layer_list[-1]:
                f.write ( '        "filename": "' + rel_file_name + '",\n' )
                f.write ( '        "align_to_next_pars": {\n' )
                f.write ( '          "window_size": ' + str(a.trans_ww) + ',\n' )
                f.write ( '          "addx": ' + str(a.trans_addx) + ',\n' )
                f.write ( '          "addy": ' + str(a.trans_addy) + ',\n' )
                f.write ( '          "output_level": 0\n' )
                f.write ( '        }\n' )
                f.write ( '      },\n' )
              else:
                f.write ( '        "filename": "' + rel_file_name + '"\n' )
                f.write ( '      }\n' )
            f.write ( '    ]\n' )
            f.write ( '  }\n' )
            f.write ( '}\n' )

      #global project_path
      #project_path = None


    elif command == "ClearAll":

      clear_all = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="Remove All?")
      response = clear_all.run()
      if response == gtk.RESPONSE_OK:
        print ( "Clearing all images..." )
        alignment_layer_index = 0
        alignment_layer_list = []
      zpa_original.queue_draw()
      for w in extra_windows_list:
        w['drawing_area'].queue_draw()
      clear_all.destroy()

    elif command == "LimScroll":
      zpa_original.max_zoom_count = 10
      zpa_original.min_zoom_count = -15

    elif command == "UnLimScroll":
      zpa_original.max_zoom_count = 1000
      zpa_original.min_zoom_count = -1500

    elif command == "Refresh":
      refresh_all_images()

    elif command == "ImCenter":
      print ( "Centering images" )
      center_all_images()

    elif command == "Spots":
      global show_spots
      show_spots = not show_spots
      print ( "Showing Spots is now " + str(show_spots) + ". Re-align to see the effect." )
      zpa.queue_draw()

    elif command == "PtMode":
      global point_mode
      point_mode = not point_mode
      print ( "Point mode is now " + str(point_mode) )
      cursor = gtk.gdk.ARROW
      if point_mode:
        cursor = gtk.gdk.HAND2
      zpa.set_cursor ( cursor )
      zpa.queue_draw()
      for w in extra_windows_list:
        w['win'].set_cursor ( cursor )
        w['drawing_area'].queue_draw()
        # Only need to set the first one since the others won't use this.
        break

    elif command == "Exit":
      get_exit = gtk.MessageDialog(flags=gtk.DIALOG_MODAL, type=gtk.MESSAGE_WARNING, buttons=gtk.BUTTONS_OK_CANCEL, message_format="Exit?")
      response = get_exit.run()
      if response == gtk.RESPONSE_OK:
        print ( "Exiting." )
        get_exit.destroy()
        exit()
      get_exit.destroy()
    else:
      print ( "Menu option \"" + command + "\" is not handled yet." )
  return True

def center_all_images():

  if len(alignment_layer_list) > 0:
    # Start with the original image
    win_size = zpa_original.drawing_area.window.get_size()

    pix_buf = None
    if zpa_original.window_index < 0:
      # Draw nothing
      # pix_buf = alignment_layer_list[alignment_layer_index].base_annotated_image.image
      pass
    else:
      # Draw one of the extra images
      pix_buf = alignment_layer_list[alignment_layer_index].image_list[zpa_original.window_index].image
    if not (pix_buf is None):
      img_w = pix_buf.get_width()
      img_h = pix_buf.get_height()
      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      zpa_original.set_scale_to_fit ( 0, img_w, 0, img_h, win_size[0], win_size[1])
      zpa_original.queue_draw()

    # Do the remaining windows
    for win_and_area in extra_windows_list:
      zpa_next = win_and_area['win']
      win_size = zpa_next.drawing_area.window.get_size()
      pix_buf = None
      if zpa_next.window_index < 0:
        # Draw nothing
        #pix_buf = alignment_layer_list[alignment_layer_index].base_annotated_image.image
        pass
      else:
        # Draw one of the extra images
        pix_buf = alignment_layer_list[alignment_layer_index].image_list[zpa_next.window_index].image
      if not (pix_buf is None):
        img_w = pix_buf.get_width()
        img_h = pix_buf.get_height()
        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        zpa_next.set_scale_to_fit ( 0, img_w, 0, img_h, win_size[0], win_size[1])
        zpa_next.queue_draw()

def refresh_all_images():
  # Determine how many windows are needed and create them as needed
  max_extra_images = 0
  for a in alignment_layer_list:
    if len(a.image_list) > 0:
      max_extra_images = max(max_extra_images, len(a.image_list))
  if max_extra_images < 1:
    # Must always keep one window
    max_extra_images = 1
  print ( "Max extra = " + str(max_extra_images) )
  num_cur_extra_images = len(extra_windows_list)
  if num_cur_extra_images > max_extra_images:
    # Remove the difference:
    for i in range(num_cur_extra_images - max_extra_images):
      rem_window_callback ( zpa_original )
  elif num_cur_extra_images < max_extra_images:
    # Add the difference
    add_window_callback ( zpa_original )


# Create the window and connect the events
def main():

  global gui_fields
  global window

  # Create a top-level GTK window
  window = gtk.Window ( gtk.WINDOW_TOPLEVEL )
  window.set_title ( "Python GTK version of SWiFT-GUI" )

  # Create a zoom/pan area to hold all of the drawing

  global zpa_original
  zpa_original = zoom_window(window,global_win_width,global_win_height,"Python GTK version of SWiFT-GUI")

  zpa_original.user_data = {
                    'image_frame'        : None,
                    'image_frames'       : [],
                    'frame_number'       : -1,
                    'display_time_index' : -1,
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

  # Create a "File" menu
  (file_menu, file_item) = zpa_original.add_menu ( "_File" )
  if True: # An easy way to indent and still be legal Python
    zpa_original.add_menu_item ( file_menu, menu_callback, "New Project",  ("NewProj", zpa_original ) )
    zpa_original.add_menu_item ( file_menu, menu_callback, "Open Project",  ("OpenProj", zpa_original ) )
    zpa_original.add_menu_item ( file_menu, menu_callback, "Save Project",  ("SaveProj", zpa_original ) )
    zpa_original.add_menu_item ( file_menu, menu_callback, "Save Project As...",  ("SaveProjAs", zpa_original ) )
    zpa_original.add_menu_sep  ( file_menu )
    zpa_original.add_menu_item ( file_menu, menu_callback, "Set Destination",  ("SetDest", zpa_original ) )
    zpa_original.add_menu_sep  ( file_menu )
    zpa_original.add_menu_item ( file_menu, menu_callback, "List >",  ("List", zpa_original ) )
    zpa_original.add_menu_item ( file_menu, menu_callback, "Exit",       ("Exit", zpa_original ) )

  # Create an "Images" menu
  (image_menu, image_item) = zpa_original.add_menu ( "_Images" )
  if True: # An easy way to indent and still be legal Python
    zpa_original.add_menu_item ( image_menu, menu_callback, "Import...",  ("ImImport", zpa_original ) )
    zpa_original.add_menu_sep  ( image_menu )
    zpa_original.add_menu_item ( image_menu, menu_callback, "Center",  ("ImCenter", zpa_original ) )
    zpa_original.add_menu_item ( image_menu, menu_callback, "Actual Size",  ("ActSize", zpa_original ) )
    zpa_original.add_menu_item ( image_menu, menu_callback, "Refresh",  ("Refresh", zpa_original ) )
    zpa_original.add_menu_sep  ( image_menu )
    zpa_original.add_menu_item ( image_menu, menu_callback, "Clear Out Images",  ("ClearOut", zpa_original ) )
    zpa_original.add_menu_sep  ( image_menu )
    zpa_original.add_menu_item ( image_menu, menu_callback, "Clear All Images",  ("ClearAll", zpa_original ) )

  # Create a "Set" menu
  (set_menu, set_item) = zpa_original.add_menu ( "_Set" )
  if True: # An easy way to indent and still be legal Python
    zpa_original.add_menu_item ( set_menu, menu_callback, "Limited Scroll",   ("LimScroll", zpa_original ) )
    zpa_original.add_menu_item ( set_menu, menu_callback, "UnLimited Scroll",   ("UnLimScroll", zpa_original ) )
    zpa_original.add_menu_item ( set_menu, menu_callback, "Pick Points",   ("PtMode", zpa_original ) )
    zpa_original.add_menu_item ( set_menu, menu_callback, "Debug",   ("Debug", zpa_original ) )

  # Create a "Show" menu
  (show_menu, show_item) = zpa_original.add_menu ( "_Show" )
  if True: # An easy way to indent and still be legal Python
    zpa_original.add_menu_item ( show_menu, menu_callback, "Spots",   ("Spots", zpa_original ) )
    zpa_original.add_menu_item ( show_menu, menu_callback, "Affine",   ("Affine", zpa_original ) )

  # Create a "Help" menu
  (help_menu, help_item) = zpa_original.add_menu ( "_Help" )
  if True: # An easy way to indent and still be legal Python
    zpa_original.add_menu_item ( help_menu, menu_callback, "Manual...",   ("Manual", zpa_original ) )
    zpa_original.add_menu_item ( help_menu, menu_callback, "Key commands...",   ("Key Commands", zpa_original ) )
    zpa_original.add_menu_item ( help_menu, menu_callback, "Mouse clicks...",   ("Mouse Clicks", zpa_original ) )
    zpa_original.add_menu_sep  ( help_menu )
    zpa_original.add_menu_item ( help_menu, menu_callback, "License...",   ("License", zpa_original ) )
    zpa_original.add_menu_item ( help_menu, menu_callback, "Version...",   ("Version", zpa_original ) )

  # Append the menus to the menu bar itself
  menu_bar.append ( file_item )
  menu_bar.append ( image_item )
  menu_bar.append ( set_item )
  menu_bar.append ( show_item )
  menu_bar.append ( help_item )

  # Show the menu bar itself (everything must be shown!!)
  menu_bar.show()

  # Create the horizontal image box
  global image_hbox
  image_hbox = gtk.HBox ( True, 0 )
  global extra_windows_list
  extra_windows_list = []

  # The zoom/pan area has its own drawing area (that it zooms and pans)
  original_drawing_area = zpa_original.get_drawing_area()

  win_and_area = { "win":zpa_original, "drawing_area":original_drawing_area }
  extra_windows_list.append ( win_and_area )

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

  a_label = gtk.Label("Translation Pass:")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  # The variable "label_entry" is used for a transient hbox containing a label and an entry
  # The variable
  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("WW:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.trans_ww_entry = gtk.Entry(5)
  gui_fields.trans_ww_entry.set_text ( str(alignment_layer_defaults.trans_ww) )
  label_entry.pack_start ( gui_fields.trans_ww_entry, True, True, 0 )
  gui_fields.trans_ww_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addx:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.trans_addx_entry = gtk.Entry(6)
  gui_fields.trans_addx_entry.set_text ( str(alignment_layer_defaults.trans_addx) )
  label_entry.pack_start ( gui_fields.trans_addx_entry, True, True, 0 )
  gui_fields.trans_addx_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addy:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.trans_addy_entry = gtk.Entry(6)
  gui_fields.trans_addy_entry.set_text ( str(alignment_layer_defaults.trans_addy) )
  label_entry.pack_start ( gui_fields.trans_addy_entry, True, True, 0 )
  gui_fields.trans_addy_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label(" ")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.skip_check_box = gtk.CheckButton("Skip")
  label_entry.pack_start ( gui_fields.skip_check_box, True, True, 0 )
  gui_fields.skip_check_box.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  # Create a horizontal box to hold a row of controls
  controls_hbox = gtk.HBox ( False, 10 )
  controls_hbox.show()
  controls_vbox.pack_start ( controls_hbox, False, False, 0 )

  a_label = gtk.Label(" ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()

  gui_fields.affine_check_box = gtk.CheckButton("  Affine Pass:")
  gui_fields.affine_check_box.set_active(True)
  controls_hbox.pack_start ( gui_fields.affine_check_box, True, True, 0 )
  gui_fields.affine_check_box.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("WW:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.affine_ww_entry = gtk.Entry(5)
  gui_fields.affine_ww_entry.set_text ( str(alignment_layer_defaults.affine_ww) )
  label_entry.pack_start ( gui_fields.affine_ww_entry, True, True, 0 )
  gui_fields.affine_ww_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addx:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.affine_addx_entry = gtk.Entry(6)
  gui_fields.affine_addx_entry.set_text ( str(alignment_layer_defaults.affine_addx) )
  label_entry.pack_start ( gui_fields.affine_addx_entry, True, True, 0 )
  gui_fields.affine_addx_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  label_entry = gtk.HBox ( False, 5 )
  a_label = gtk.Label("Addy:")
  label_entry.pack_start ( a_label, True, True, 0 )
  a_label.show()
  gui_fields.affine_addy_entry = gtk.Entry(6)
  gui_fields.affine_addy_entry.set_text ( str(alignment_layer_defaults.affine_addy) )
  label_entry.pack_start ( gui_fields.affine_addy_entry, True, True, 0 )
  gui_fields.affine_addy_entry.show()
  controls_hbox.pack_start ( label_entry, True, True, 0 )
  label_entry.show()


  a_label = gtk.Label(" ")
  controls_hbox.pack_start ( a_label, True, True, 0 )
  a_label.show()


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

  button = gtk.Button("Abort")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", stop_callback, zpa_original )
  button.show()

  button = gtk.Button("+")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", add_window_callback, zpa_original )
  button.show()

  button = gtk.Button("-")
  controls_hbox.pack_start ( button, True, True, 0 )
  button.connect_object ( "clicked", rem_window_callback, zpa_original )
  button.show()

  # Show the main window
  window.show()

  # This is now for point picking mode:  zpa_original.set_cursor ( gtk.gdk.HAND2 )

  gtk.idle_add ( background_callback, zpa_original )

  # Turn control over to GTK to run everything from here onward.
  gtk.main()
  return 0


if __name__ == '__main__':
  main()
