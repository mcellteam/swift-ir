#!/usr/bin/env python

#__import__('code').interact(local = locals())
import time
import os

import pygtk
pygtk.require('2.0')
import gobject
import gtk

import app_window

global zpa_original
global zpa_aligned

def expose_callback ( drawing_area, event, zpa ):
  diff_2d_sim = zpa.user_data['diff_2d_sim']
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

  if zpa.user_data['image_frame']:

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
    pix_buf = zpa.user_data['image_frame']
    pbw = pix_buf.get_width()
    pbh = pix_buf.get_height()
    scale_w = zpa.ww(pbw) / pbw
    scale_h = zpa.wh(pbh) / pbh
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

    scaled_image = pix_buf.scale_simple( int(pbw*scale_w), int(pbh*scale_h), gtk.gdk.INTERP_NEAREST )
    drawable.draw_pixbuf ( gc, scaled_image, 0, 0, zpa.wxi(0), zpa.wyi(0), -1, -1, gtk.gdk.RGB_DITHER_NONE )

    # print ( "Zoom Scale = " + str(zpa.zoom_scale) )

    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

  gc.foreground = colormap.alloc_color(32767,32767,32767)
  drawable.draw_line ( gc, width-1, 0, width-1, height )

  # Restore the previous color
  gc.foreground = old_fg
  return False


def step_callback(zpa):
  diff_2d_sim = zpa.user_data['diff_2d_sim']
  display_time_index = zpa.user_data['display_time_index']
  diff_2d_sim.step()
  zpa.get_drawing_area().queue_draw()
  return True


def step_in_callback(zpa):
  diff_2d_sim = zpa.user_data['diff_2d_sim']
  diff_2d_sim.step_in()
  zpa.get_drawing_area().queue_draw()
  return True

def step_10_callback(zpa):
  for i in range(10):
    step_callback(drawing_area)
  return True

def dump_callback(zpa):
  diff_2d_sim = zpa.user_data['diff_2d_sim']
  diff_2d_sim.print_self()
  return True

def reset_callback(zpa):
  # This creates a new simulation
  zpa.user_data['diff_2d_sim'] = diff_2d_sim()
  zpa.user_data['display_time_index'] = -1
  zpa.get_drawing_area().queue_draw()


def background_callback ( zpa ):
  if zpa.user_data['running']:
    t = time.time()
    if t - zpa.user_data['last_update'] > zpa.user_data['frame_delay']:
      zpa.user_data['last_update'] = t
      step_callback(zpa)
      print ( "  Running at time = " + str(t) )
      zpa.queue_draw()
  return True

def run_callback ( zpa ):
  # print ( "Run " )
  zpa.user_data['running'] = True
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
    global zpa_original
    global zpa_aligned
    if command == "Fast":
      zpa.user_data['frame_delay'] = 0.01
    elif command == "Med":
      zpa.user_data['frame_delay'] = 0.1
    elif command == "Slow":
      zpa.user_data['frame_delay'] = 1.0
    elif command == "ToggleLegend":
      zpa.user_data['show_legend'] = not zpa.user_data['show_legend']
      zpa.queue_draw()
    elif command == "Debug":
      __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
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
        file_name_list = file_chooser.get_filenames()
        print ( "Selected Files: " + str(file_name_list) )
        #filename = file_chooser.get_filename()
        #file_chooser.destroy()

      file_chooser.destroy()
      print ( "Done with dialog" )
      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      zpa.queue_draw()
    elif command == "LimScroll":
      zpa_original.max_zoom_count = 10
      zpa_original.min_zoom_count = -15
      zpa_aligned.max_zoom_count = 10
      zpa_aligned.min_zoom_count = -15
    elif command == "UnLimScroll":
      zpa_original.max_zoom_count = 100
      zpa_original.min_zoom_count = -150
      zpa_aligned.max_zoom_count = 100
      zpa_aligned.min_zoom_count = -150

    else:
      print ( "Menu option \"" + command + "\" is not handled yet." )
  return True


# Minimized stub of the previous 2D Simulation
class point_face_object:
  def __init__( self, name="", x=0, y=0, color=(32000,32000,32000), points=[], faces=[] ):
    self.name = name
    self.color = color
    self.points = [ p for p in points ]
    self.faces = [ f for f in faces ]
    self.x = x
    self.y = y
    if (len(points) > 0) and (len(faces) == 0):
      # Make faces for the points
      for i in range(len(self.points)):
        print ( "  Making face with " + str(i) + "," + str((i+1)%len(self.points)) )
        self.faces.append ( (i, (i+1)%len(self.points)) )
  def print_self ( self ):
    print ( "Object " + self.name + ": x,y = (" + str(self.x) + "," + str(self.y) )
    for point in self.points:
      print ( "  " + str(point) )
    for face in self.faces:
      print ( "  " + str(face) )

class diff_2d_sim:
  def __init__ ( self ):
    print ( " Constructing a new minimal simulation" )
    self.objects = [
        point_face_object ( "Triangle 1", x=80, y=0, points=[[0,100], [50,-10], [-50,-10]] ),
        point_face_object ( "Square 1", x=0, y=0, points=[[-90,-90], [-90,90], [90,90], [90,-90]] )
      ]
    # Set some simulation values
    self.t = 0
    self.dt = 2

  def step ( self ):
    print ( "Before run(1): t=" + str(self.t) )
    self.t += self.dt
    print ( "After run(1): t=" + str(self.t) )

  def step_in ( self ):
    print ( "Before step_in(): t=" + str(self.t) )
    self.t += self.dt
    print ( "After step_in(): t=" + str(self.t) )

  def print_self ( self ):
    print ( "t = " + str(self.t) )



# Create the window and connect the events
def main():

  # Create a top-level GTK window
  window = gtk.Window ( gtk.WINDOW_TOPLEVEL )
  window.set_title ( "Python GTK version of SWiFT-GUI" )

  # Create a zoom/pan area to hold all of the drawing

  global zpa_original
  zpa_original = app_window.zoom_pan_area(window,800,800,"Python GTK version of SWiFT-GUI")
  global zpa_aligned
  zpa_aligned = app_window.zoom_pan_area(window,800,800,"Python GTK version of SWiFT-GUI")

  zpa_original.user_data = {
                    'image_frame'        : None,
                    'image_frames'       : [],
                    'frame_number'       : -1,
                    'diff_2d_sim'        : diff_2d_sim(),
                    'display_time_index' : -1,
                    'running'            : False,
                    'last_update'        : -1,
                    'show_legend'        : True,
                    'frame_delay'        : 0.1,
                    'size'               : 1.0
                  }

  zpa_aligned.user_data = {
                    'image_frame'        : None,
                    'image_frames'       : [],
                    'frame_number'       : -1,
                    'diff_2d_sim'        : diff_2d_sim(),
                    'display_time_index' : -1,
                    'running'            : False,
                    'last_update'        : -1,
                    'show_legend'        : True,
                    'frame_delay'        : 0.1,
                    'size'               : 1.0
                  }

  # Set the relationships between "user" coordinates and "screen" coordinates

  zpa_aligned.set_x_scale ( 0.0, 300, 100.0, 400 )
  zpa_aligned.set_y_scale ( 0.0, 250 ,100.0, 350 )

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
  menu_bar.append ( help_item )

  # Show the menu bar itself (everything must be shown!!)
  menu_bar.show()

  # Create the horizontal image box
  image_hbox = gtk.HBox ( True, 0 )

  # The zoom/pan area has its own drawing area (that it zooms and pans)
  drawing_area = zpa_original.get_drawing_area()
  drawing_area2 = zpa_aligned.get_drawing_area()

  # Add the zoom/pan area to the vertical box (becomes the main area)
  image_hbox.pack_start(drawing_area, True, True, 0)
  # fake_out_panel = gtk.Button("Output")
  image_hbox.pack_start(drawing_area2, True, True, 0)
  image_hbox.show()
  main_win_vbox.pack_start(image_hbox, True, True, 0)
  drawing_area.show()
  drawing_area2.show()

  # The zoom/pan area doesn't draw anything, so add our custom expose callback
  drawing_area.connect ( "expose_event", expose_callback, zpa_original )
  drawing_area2.connect ( "expose_event", expose_callback, zpa_aligned )

  # Set the events that the zoom/pan area must respond to
  #  Note that zooming and panning requires button press and pointer motion
  #  Other events can be set and handled by user code as well
  drawing_area.set_events ( gtk.gdk.EXPOSURE_MASK
                          | gtk.gdk.LEAVE_NOTIFY_MASK
                          | gtk.gdk.BUTTON_PRESS_MASK
                          | gtk.gdk.POINTER_MOTION_MASK
                          | gtk.gdk.POINTER_MOTION_HINT_MASK )

  # Create a horizontal box to hold application buttons
  controls_hbox = gtk.HBox ( True, 0 )
  controls_hbox.show()
  main_win_vbox.pack_start ( controls_hbox, False, False, 0 )

  # Add some application specific buttons and their callbacks

  step_button = gtk.Button("Step")
  controls_hbox.pack_start ( step_button, True, True, 0 )
  step_button.connect_object ( "clicked", step_callback, zpa_original )
  step_button.show()

  run_button = gtk.Button("Run")
  controls_hbox.pack_start ( run_button, True, True, 0 )
  run_button.connect_object ( "clicked", run_callback, zpa_original )
  run_button.show()

  stop_button = gtk.Button("Stop")
  controls_hbox.pack_start ( stop_button, True, True, 0 )
  stop_button.connect_object ( "clicked", stop_callback, zpa_original )
  stop_button.show()

  dump_button = gtk.Button("Dump")
  controls_hbox.pack_start ( dump_button, True, True, 0 )
  dump_button.connect_object ( "clicked", dump_callback, zpa_original )
  dump_button.show()

  reset_button = gtk.Button("Reset")
  controls_hbox.pack_start ( reset_button, True, True, 0 )
  reset_button.connect_object ( "clicked", reset_callback, zpa_original )
  reset_button.show()



  zpa_original.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_file ( ".." + os.sep + "vj_097_1_mod.jpg" )
  zpa_aligned.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_file ( ".." + os.sep + "vj_097_2_mod.jpg" )


  # Show the main window
  window.show()

  zpa_original.set_cursor ( gtk.gdk.HAND2 )

  gtk.idle_add ( background_callback, zpa_original )
  gtk.idle_add ( background_callback, zpa_aligned )

  # Turn control over to GTK to run everything from here onward.
  gtk.main()
  return 0


if __name__ == '__main__':
  main()
