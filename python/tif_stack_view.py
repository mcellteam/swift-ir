#!/usr/bin/env python

#__import__('code').interact(local = locals())
import time
import os
import subprocess
import struct

import pygtk
pygtk.require('2.0')
import gobject
import gtk

import app_window

debug_level = 0
def print_debug ( level, str ):
  global debug_level
  if level < debug_level:
    print ( str )

class image_layer:
  def __init__ ( self, original_image_name=None, ptiled_image_name=None ):
    self.original_image_name = original_image_name
    self.ptiled_image_name = ptiled_image_name
    self.tiff_struct = None

  def load_tiff_structure ( self ):
    self.tiff_struct = pyramid_tiff ( self.ptiled_image_name )


class tag_record:
  def __init__ ( self, tag, tagtype, tagcount, tagvalue ):
    self.tag = tag
    self.tagtype = tagtype
    self.tagcount = tagcount
    self.tagvalue = tagvalue
  def __repr__ ( self ):
    return ( "TR: " + str(self.tag) + ", " + str(self.tagtype) + ", " + str(self.tagcount) + ", " + str(self.tagvalue) )

class image_record:
  def __init__ ( self ):
    self.bps = None
    self.width = None
    self.height = None
    self.tile_width = None
    self.tile_length = None
    self.tile_offsets = []
    self.tile_counts = []
    self.tag_record_list = []
  #def __repr__ ( self ):
  #  return ( "IR: " + str(self.width) + ", " + str(self.height) )


class pyramid_tiff:
  ''' This is an abstraction of a tiled tiff file to use for testing faster image display '''

  def __repr__ ( self ):
    tile_data_str = None
    f = open ( self.file_name, 'rb' )
    if len(self.tile_offsets) > 0:
      # Seek to the last one
      f.seek ( self.tile_offsets[-1] )
      image_data = f.read ( self.tile_counts[-1] )
      print_debug ( 50, "Read " + str(self.tile_counts[-1]) + " bytes at " + str(self.tile_offsets[-1]) + " from " + str(self.file_name) )
      tile_data_str = str([ord(d) for d in image_data[0:20]])
      print_debug ( 50, "  " + tile_data_str )
    return ( tile_data_str )

  def __init__ ( self, file_name ):

    self.file_name = file_name
    self.endian = '<' # Intel format
    self.image_list = []
    self.tile_width = -1
    self.tile_length = -1
    self.tile_offsets = []
    self.tile_counts = []

    print_debug ( 50, "Reading from TIFF: " + str(file_name) )

    with open ( self.file_name, 'rb' ) as f:

      d = f.read(50)
      print_debug ( 50, "Tiff Data: " + str([ord(c) for c in d]) )
      f.seek(0)

      d = [ord(c) for c in f.read(4)] # Read 4 bytes of the header
      if   d == [0x49, 0x49, 0x2a, 0x00]:
        print_debug ( 50, "This is a TIFF file with Intel (little endian) byte ordering" )
        self.endian = '<' # Intel format
      elif d == [0x4d, 0x4d, 0x00, 0x2a]:
        print_debug ( 50, "This is a TIFF file with Motorola (big endian) byte ordering" )
        self.endian = '>' # Motorola format
      else:
        print_debug ( 50, "This is not a TIFF file" )
        self.endian = None
        return

      # Read the offset of the first image directory from the header
      offset = struct.unpack_from ( self.endian+"L", f.read(4), offset=0 )[0]
      print_debug ( 50, "Offset = " + str(offset) )

      dir_num = 1

      while offset > 0:
        this_image = image_record()
        f.seek ( offset )
        numDirEntries = struct.unpack_from ( self.endian+'H', f.read(2), offset=0 )[0]
        offset += 2
        print_debug ( 50, "Directory " + str(dir_num) + " has NumDirEntries = " + str(numDirEntries) )
        dir_num += 1
        # Read the tags
        f.seek ( offset )
        for tagnum in range(numDirEntries):
          tagtuple = struct.unpack_from ( self.endian+'HHLL', f.read(12), offset=0 )
          tag = tagtuple[0]
          tagtype = tagtuple[1]
          tagcount = tagtuple[2]
          tagvalue = tagtuple[3]
          this_image.tag_record_list.append ( tag_record ( tag, tagtype, tagcount, tagvalue ) )
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
                print_debug ( 50, "     Decoding error for " + str(struct.unpack_from ( self.endian+'s', f.read(2), offset=tagvalue+i )[0]) + " in following tag:" )
            if len(ascii_str) > 60:
              ascii_str = ascii_str[0:60]
            ascii_str = ascii_str.replace ( "\n", " " )
            ascii_str = ascii_str.replace ( "\r", " " )
            tagstr += ascii_str + "\""
          '''
          print_debug ( 50, "  Tag = " + str(tagtuple) + " = " + tagstr )
        self.image_list.append ( this_image )
        f.seek ( offset )
        nextIFDOffset = struct.unpack_from ( self.endian+'L', f.read(4), offset=0 )[0]
        offset = nextIFDOffset
        print_debug ( 50, "\n" )

      print_debug ( 50, "\n\n" )
      print_debug ( 50, 120*"=" )
      print_debug ( 50, "\n\n" )

      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      image_num = 1
      for this_image in self.image_list:
        print_debug ( 50, "Image " + str(image_num) + ":\n" )
        image_num += 1

        for tag_rec in this_image.tag_record_list:
          print_debug ( 50, "  Tag: " + str(tag_rec) )
          if tag_rec.tag == 256:
            this_image.width = tag_rec.tagvalue
            print_debug ( 50, "    Width: " + str(this_image.width) )
          if tag_rec.tag == 257:
            this_image.height = tag_rec.tagvalue
            print_debug ( 50, "    Height: " + str(this_image.height) )
          if tag_rec.tag == 258:
            this_image.bps = tag_rec.tagvalue
            print_debug ( 50, "    Bits/Samp: " + str(this_image.bps) )
            if this_image.bps != 8:
              print_debug ( 50, "Can't handle files with " + str(this_image.bps) + " bits per sample" )
              exit ( 0 )
          if tag_rec.tag == 322:
            this_image.tile_width = tag_rec.tagvalue
            print_debug ( 50, "    TileWidth: " + str(this_image.tile_width) )
          if tag_rec.tag == 323:
            this_image.tile_length = tag_rec.tagvalue
            print_debug ( 50, "    TileLength: " + str(this_image.tile_length) )
          if tag_rec.tag == 324:
            print_debug ( 50, "    TileOffsets: " + str(tag_rec.tagvalue) )
            if tag_rec.tagcount == 1:
              # Special case where the offset is the tagvalue?
              this_image.tile_offsets = ( tag_rec.tagvalue, )
            else:
              f.seek ( tag_rec.tagvalue )
              this_image.tile_offsets = struct.unpack_from ( self.endian+(tag_rec.tagcount*"L"), f.read(4*tag_rec.tagcount), offset=0 )
            self.tile_offsets = this_image.tile_offsets
            print_debug ( 50, "       " + str(this_image.tile_offsets) )
          if tag_rec.tag == 325:
            print_debug ( 50, "    TileByteCounts: " + str(tag_rec.tagvalue) )
            if tag_rec.tagcount == 1:
              # Special case where the count is the tagvalue?
              this_image.tile_counts = ( tag_rec.tagvalue, )
            else:
              f.seek ( tag_rec.tagvalue )
              this_image.tile_counts = struct.unpack_from ( self.endian+(tag_rec.tagcount*"L"), f.read(4*tag_rec.tagcount), offset=0 )
            self.tile_counts = this_image.tile_counts
            print_debug ( 50, "       " + str(this_image.tile_counts) )

        print_debug ( 50, "  bps:" + str(this_image.bps) +
                ", width:" + str(this_image.width) +
                ", height:" + str(this_image.height) +
                ", tile_width:" + str(this_image.tile_width) +
                ", tile_length:" + str(this_image.tile_length) +
                ", tile_offsets:" + str(this_image.tile_offsets) +
                ", tile_counts:" + str(this_image.tile_counts) )


        if not (None in (this_image.bps, this_image.width, this_image.height, this_image.tile_width, this_image.tile_length, this_image.tile_offsets, this_image.tile_counts)):
          print_debug ( 50, "\nRead from a block of tiles ...\n" )
          for i in range(len(this_image.tile_offsets)):
            offset = this_image.tile_offsets[i]
            count = this_image.tile_counts[i]
            f.seek ( offset )
            data = struct.unpack_from ( self.endian+"BBBB", f.read(4), offset=0 )
            #print_debug ( 50, "Read data " + str(data) + " from " + str(offset) )
            print_debug ( 50, "" )

        '''
        if not (None in (bps, w, h, tw, tl, to, tc)):
          print_debug ( 50, "\nFound a block of tiles:\n" )
          for i in range(len(offsets)):
            offset = offsets[i]
            count = counts[i]
            f.seek ( offset )
            data = struct.unpack_from ( self.endian+(count*"B"), f.read(count), offset=0 )
            for r in range(tl):
              print_debug ( 50, str ( [ data[(r*tw)+d] for d in range(tw) ] ) )
            print_debug ( 50, "" )
        '''

        # offset = 0 ############ Force a stop


      print_debug ( 50, "\n\n" )

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




def expose_callback ( drawing_area, event, zpa ):
  print_debug ( 50, "Redrawing" )
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

  if not (zpa.user_data['image_frame'] is None):

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

    # print_debug ( 50, "Zoom Scale = " + str(zpa.zoom_scale) )

    # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

  # Restore the previous color
  gc.foreground = old_fg
  return False


b64    =     [ chr(ord('A')+i) for i in range(26) ]
b64.extend ( [ chr(ord('a')+i) for i in range(26) ] )
b64.extend ( [ chr(ord('0')+i) for i in range(10) ] )
b64.extend ( [ '+', '/' ] )


def get_image_data(zpa):
  global b64

  if zpa.user_data['tile_number'] == -2:
    #print ( "Test XPM -2" )
    xpm = [
    "16 16 3 1",
    "       c None",
    ".      c #000000",
    "X      c #FFFFFF",
    "                ",
    "   ......       ",
    "   .XXX.X.      ",
    "   .XXX.XX.     ",
    "   .XXX.XXX.    ",
    "   .XXX.....    ",
    "   .XXXXXXX.    ",
    "   .XXXXXXX.    ",
    "   .XXXXXXX.    ",
    "   .XXXXXXX.    ",
    "   .XXXXXXX.    ",
    "   .XXXXXXX.    ",
    "   .XXXXXXX.    ",
    "   .........    ",
    "                ",
    "                "
    ]

    nr = 100
    nc = 100
    xpm = [ str(nr) + " " + str(nc) + " 16 1" ]
    for i in range ( 16 ):
      h = hex(i)[2]
      k = chr(ord('a') + i)
      xpm.append ( str(k) + " c #" + h + h + h  )

    data = ""
    for i in range (nr):
      for j in range (nr):
        data += ( chr ( ord('a') + ((i*j) % 256)/16 ) )
      xpm.append ( data )
      data = ""

    zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_xpm_data ( xpm )

  elif zpa.user_data['tile_number'] == -3:

    #print ( "Test 4 bit XPM -3" )

    print_debug ( 50, "New layer index = " + str(zpa.user_data['layer_index']) )
    layer = zpa.user_data['image_layers'][zpa.user_data['layer_index']]
    print_debug ( 50, "Image file = " + str(layer.ptiled_image_name) )

    #zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_file ( layer.ptiled_image_name )

    f = open ( layer.ptiled_image_name, 'rb' )
    img_tile = layer.tiff_struct.image_list[zpa.user_data['tile_number']]
    f.seek ( img_tile.tile_offsets[0] )
    d = f.read ( img_tile.tile_counts[0] )

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

    nr = img_tile.tile_length
    nc = img_tile.tile_width
    xpm = [ str(nr) + " " + str(nc) + " 16 1" ]
    for i in range ( 16 ):
      h = hex(i)[2]
      k = chr(ord('a') + i)
      xpm.append ( str(k) + " c #" + h + h + h  )

    data = ""
    for r in range (nr):
      for c in range (nc):
        i = (r*256) + c
        data += ( chr ( ord('a') + (ord(d[i]) % 256)/16 ) )
      xpm.append ( data )
      data = ""

    zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_xpm_data ( xpm )

  elif zpa.user_data['tile_number'] == -4:

    #print ( "Test 6 bit XPM -4" )
    if len(zpa.user_data['image_layers']) > 0:

      print_debug ( 50, "New layer index = " + str(zpa.user_data['layer_index']) )
      layer = zpa.user_data['image_layers'][zpa.user_data['layer_index']]
      print_debug ( 50, "Image file = " + str(layer.ptiled_image_name) )

      #zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_file ( layer.ptiled_image_name )

      f = open ( layer.ptiled_image_name, 'rb' )
      img_tile = layer.tiff_struct.image_list[zpa.user_data['tile_number']]
      f.seek ( img_tile.tile_offsets[0] )
      d = f.read ( img_tile.tile_counts[0] )

      #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      nr = img_tile.tile_length
      nc = img_tile.tile_width

      xpm = [ str(nr) + " " + str(nc) + " 64 1" ]
      for i in range ( 64 ):
        h = hex(4*i)[2:]
        if len(h) <= 1: h = '0' + h
        k = b64[i]
        xpm.append ( str(k) + " c #" + h + h + h  )

      data = ""
      for r in range (nr):
        for c in range (nc):
          i = (r*256) + c
          bindex = (ord(d[i])%256)/4
          data += b64[bindex]
        xpm.append ( data )
        data = ""

      zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_xpm_data ( xpm )

  else:

    print ( "Get an actual tile for tile # " + str(zpa.user_data['tile_number']) )

    if len(zpa.user_data['image_layers']) > 0:

      # These should be positive tile numbers:

      if True:

        print_debug ( 50, "New layer index = " + str(zpa.user_data['layer_index']) )
        layer = zpa.user_data['image_layers'][zpa.user_data['layer_index']]
        print_debug ( 50, "Image file = " + str(layer.ptiled_image_name) )

        f = open ( layer.ptiled_image_name, 'rb' )
        img = layer.tiff_struct.image_list[zpa.user_data['selected_image']]
        #img_tile = layer.tiff_struct.image_list[zpa.user_data['selected_image']]
        f.seek ( img.tile_offsets[0] )
        d = f.read ( img.tile_counts[0] )

        nr = img.tile_length
        nc = img.tile_width

        xpm = [ str(nr) + " " + str(nc) + " 64 1" ]
        for i in range ( 64 ):
          h = hex(4*i)[2:]
          if len(h) <= 1: h = '0' + h
          k = b64[i]
          xpm.append ( str(k) + " c #" + h + h + h  )

        data = ""
        for r in range (nr):
          for c in range (nc):
            i = (r*256) + c
            bindex = (ord(d[i])%256)/4
            data += b64[bindex]
          xpm.append ( data )
          data = ""

        zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_xpm_data ( xpm )

      else:

        # Use binary file read to create the pixbuf (don't know how to do this in pyGTK)

        #>>> [ s for s in dir(gtk.gdk) if 'pixbuf' in s ]
        # ['pixbuf_get_file_info', 'pixbuf_get_formats', 'pixbuf_get_from_drawable', 'pixbuf_loader_new',
        #  'pixbuf_loader_new_with_mime_type', 'pixbuf_new_from_array', 'pixbuf_new_from_data', 'pixbuf_new_from_file',
        #  'pixbuf_new_from_file_at_scale', 'pixbuf_new_from_file_at_size', 'pixbuf_new_from_inline', 'pixbuf_new_from_stream',
        #  'pixbuf_new_from_stream_at_scale', 'pixbuf_new_from_xpm_data']
        print_debug ( 50, "New layer index = " + str(zpa.user_data['layer_index']) )
        layer = zpa.user_data['image_layers'][zpa.user_data['layer_index']]
        print_debug ( 50, "Image file = " + str(layer.ptiled_image_name) )

        #zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_file ( layer.ptiled_image_name )

        #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

        f = open ( layer.ptiled_image_name, 'rb' )
        img_tile = layer.tiff_struct.image_list[zpa.user_data['tile_number']]
        f.seek ( img_tile.tile_offsets[0] )
        d = f.read ( img_tile.tile_counts[0] )
        #d = ''.join ( [ s+s+s+chr(255) for s in d ] )
        #d = ''.join ( [ s+s+s for s in d ] )
        zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_data ( d, gtk.gdk.COLORSPACE_RGB,
                                                                      False, 8,
                                                                      img_tile.tile_width,
                                                                      img_tile.tile_length,
                                                                      img_tile.tile_width )
  zpa.queue_draw()

  #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

class zoom_panel ( app_window.zoom_pan_area ):

  def mouse_scroll_callback ( self, canvas, event, zpa ):
    ''' Overload the base mouse_scroll_callback to provide custom UNshifted action. '''

    if 'GDK_SHIFT_MASK' in event.get_state().value_names:
      # Use shifted scroll wheel to zoom the image size
      return ( app_window.zoom_pan_area.mouse_scroll_callback ( self, canvas, event, zpa ) )
    else:
      # Use normal (unshifted) scroll wheel to move through the stack
      print_debug ( 50, "Moving through the stack" )
      if len(zpa.user_data['image_layers']) <= 0:
        print_debug ( 50, "No images" )
      else:
        if event.direction == gtk.gdk.SCROLL_UP:
          if (zpa.user_data['layer_index']+1) < len(zpa.user_data['image_layers']):
            zpa.user_data['layer_index'] += 1
            get_image_data(zpa)
        elif event.direction == gtk.gdk.SCROLL_DOWN:
          if zpa.user_data['layer_index'] > 0:
            zpa.user_data['layer_index'] += -1
            get_image_data(zpa)

      zpa.queue_draw()
      return True


def step_callback(zpa):
  diff_2d_sim = zpa.user_data['diff_2d_sim']
  display_time_index = zpa.user_data['display_time_index']
  diff_2d_sim.step()
  zpa.get_drawing_area().queue_draw()
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
      print_debug ( 50, "  Running at time = " + str(t) )
      zpa.queue_draw()
  return True

def run_callback ( zpa ):
  # print_debug ( 50, "Run " )
  zpa.user_data['running'] = True
  return True

def stop_callback ( zpa ):
  # print_debug ( 50, "Stop " )
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

    if command == "ImImport":

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
        if len(file_name_list) > 0:
          try:
            os.mkdir ( "pyramid_stack" )
          except:
            # This catches directories that already exist
            pass
          print_debug ( 50, "Selected Files: " + str(file_name_list) )
          for f in file_name_list:
            base_name = f.split(os.sep)[-1]
            parent_dir = f.split(os.sep)[-2]
            if (parent_dir == "pyramid_stack") and (base_name.split('.')[-1] == "tif"):
              print_debug ( 50, "File " + base_name + " is assumed to be tiled." )
              new_layer = image_layer ( f, f )
              new_layer.load_tiff_structure()
              zpa.user_data['image_layers'].append ( new_layer )
            else:
              if '.' in base_name:
                base_name = base_name[0:base_name.rfind('.')]
              new_name = "pyramid_stack" + os.sep + base_name + '.tif'
              print_debug ( 50, "Tiling file " + str(f) + " to " + new_name )
              #p = subprocess.Popen ( ['/usr/bin/convert', f, "-compress", "None", "-depth", "8", "-define", "tiff:tile-geometry=256x256", "tif:"+new_name] )
              p = subprocess.Popen ( ['/usr/bin/convert', f, "-compress", "None", "-depth", "8", "-define", "tiff:tile-geometry=256x256", "ptif:"+new_name] )
              p.wait()
              new_layer = image_layer ( f, new_name )
              new_layer.load_tiff_structure()
              zpa.user_data['image_layers'].append ( new_layer )

      file_chooser.destroy()
      print_debug ( 50, "Done with dialog" )
      #zpa.force_center = True
      get_image_data(zpa)
      zpa.queue_draw()

    elif command == "Center":
      print_debug ( 50, "Centering" )
      zpa.queue_draw()

    elif command == "ScaleSel":
      print_debug ( 50, "Tile Size" )

      layers = zpa.user_data['image_layers']
      layer = layers[zpa.user_data['layer_index']]
      ts = layer.tiff_struct

      if zpa.user_data['selected_image'] is None:
        zpa.user_data['selected_image'] = 0
      image = ts.image_list[zpa.user_data['selected_image']]

      label = gtk.Label("Scales: 0 to " + str(len(ts.image_list)-1))
      dialog = gtk.Dialog("Enter an Image Scale",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      image_entry = gtk.Entry(20)
      image_entry.set_text ( '' )
      dialog.vbox.pack_end(image_entry)
      image_entry.show()

      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        num = int(image_entry.get_text())
        if (num >= 0) and (num < len(ts.image_list)):
          zpa.user_data['selected_image'] = num
          print ( "Selected image = " + str(zpa.user_data['selected_image']) )
        else:
          print ( "Bad image index: " + str(num) )

      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      dialog.destroy()



      '''
      width_dict = {}
      for im in ts.image_list:
        width_dict[im.width] = im

      label = gtk.Label("Tile Sizes: " + ' '.join([ str(s) for s in sorted(width_dict.keys())]) )
      dialog = gtk.Dialog("Enter a Tile Size",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      scales_entry = gtk.Entry(20)
      scales_entry.set_text ( '' )
      dialog.vbox.pack_end(scales_entry)
      scales_entry.show()


      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        zpa.user_data['selected_width'] = int(scales_entry.get_text())
        print ( "Selected width = " + str(zpa.user_data['selected_width']) )

      # __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      dialog.destroy()
      '''
      get_image_data(zpa)
      zpa.queue_draw()

    elif command == "TileSel":
      print_debug ( 50, "Tile Index" )

      layers = zpa.user_data['image_layers']
      layer = layers[zpa.user_data['layer_index']]
      ts = layer.tiff_struct
      width_dict = {}
      for im in ts.image_list:
        width_dict[im.width] = im

      label = gtk.Label("Tile Sizes: " + ' '.join([ str(s) for s in sorted(width_dict.keys())]) )
      dialog = gtk.Dialog("Enter a Tile Size",
                         None,
                         gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                         (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                          gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))
      dialog.vbox.pack_start(label)
      label.show()
      scales_entry = gtk.Entry(20)
      scales_entry.set_text ( '' )
      dialog.vbox.pack_end(scales_entry)
      scales_entry.show()

      ### zpa.user_data['tile_number']

      response = dialog.run()
      if response == gtk.RESPONSE_ACCEPT:
        zpa.user_data['selected_width'] = int(scales_entry.get_text())
        print ( "Selected width = " + str(zpa.user_data['selected_width']) )

      __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

      dialog.destroy()

      zpa.queue_draw()



    elif command == "ClearAll":
      print_debug ( 50, "Clearing all images" )
      zpa.user_data['image_frame'] = None
      zpa.user_data['layer_index'] = 0
      zpa.user_data['image_layers'] = []
      zpa.queue_draw()

    elif command == "Console":
      global debug_level
      print_debug ( -1, "Handy global items:" )
      print_debug ( -1, "  debug_level" )
      print_debug ( -1, "Handy local items:" )
      print_debug ( -1, "  widget" )
      print_debug ( -1, "  data" )
      print_debug ( -1, "  command" )
      print_debug ( -1, "  zpa" )

      __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
      zpa.queue_draw()

    elif "Tile_" in command:
      try:
        tn = int(command[len("Tile_"):])
        zpa.user_data['tile_number'] = tn
        get_image_data(zpa)
        zpa.queue_draw()
      except:
        pass

    elif "Debug_" in command:
      global debug_level
      try:
        debug_level = int(command[len("Debug_"):])
      except:
        pass

    else:
      print_debug ( 50, "Menu option \"" + command + "\" is not handled yet." )

  return True

# Minimized stub of the previous 2D Simulation
class diff_2d_sim:
  def __init__ ( self ):
    print_debug ( 50, " Constructing a new minimal simulation" )
    self.objects = []
    # Set some simulation values
    self.t = 0
    self.dt = 2

  def diffuse ( self ):
    print_debug ( 50, "Start diffuse" )
    print_debug ( 50, "End diffuse" )

  def step ( self ):
    print_debug ( 50, "Before run(1): t=" + str(self.t) )
    self.t += self.dt
    print_debug ( 50, "After run(1): t=" + str(self.t) )

  def step_in ( self ):
    print_debug ( 50, "Before step_in(): t=" + str(self.t) )
    self.t += self.dt
    print_debug ( 50, "After step_in(): t=" + str(self.t) )

  def print_self ( self ):
    print_debug ( 50, "t = " + str(self.t) )



# Create the window and connect the events
def main():

  # Create a top-level GTK window
  window = gtk.Window ( gtk.WINDOW_TOPLEVEL )
  window.set_title ( "Stack View with Python GTK" )

  # Create a zoom/pan area to hold all of the drawing
  zpa = zoom_panel(window,1200,900,"Stack View")
  zpa.user_data = { 
                    'image_frame'        : None,
                    'image_layers'       : [],
                    'layer_index'        : 0,
                    'selected_width'     : None,
                    'selected_image'     : 0,
                    'tile_number'        : 0,
                    'diff_2d_sim'        : diff_2d_sim(),
                    'display_time_index' : -1,
                    'running'            : False,
                    'last_update'        : -1,
                    'show_legend'        : True,
                    'frame_delay'        : 0.1,
                    'size'               : 1.0
                  }

  # Set the relationship between "user" coordinates and "screen" coordinates
  zpa.set_x_scale ( 0.0, 300, 100.0, 400 )
  zpa.set_y_scale ( 0.0, 250 ,100.0, 350 )

  # Create a vertical box to hold the menu, drawing area, and buttons
  vbox = gtk.VBox ( homogeneous=False, spacing=0 )
  window.add(vbox)
  vbox.show()

  # Connect GTK's "main_quit" function to the window's "destroy" event
  window.connect ( "destroy", lambda w: gtk.main_quit() )

  # Create a menu bar and add it to the vertical box
  menu_bar = gtk.MenuBar()
  vbox.pack_start(menu_bar, expand=False, fill=False, padding=0)

  # Create a "File" menu
  (file_menu, file_item) = zpa.add_menu ( "_File" )
  if True: # An easy way to indent and still be legal Python
    zpa.add_menu_item ( file_menu, menu_callback, "_Python Console",   ("Console", zpa ) )
    zpa.add_menu_item ( file_menu, menu_callback, "E_xit",       ("Exit", zpa ) )

  # Create an "Images" menu
  (images_menu, images_item) = zpa.add_menu ( "_Images" )
  if True: # An easy way to indent and still be legal Python
    zpa.add_menu_item ( images_menu, menu_callback, "_Import...",   ("ImImport", zpa ) )
    zpa.add_menu_item ( images_menu, menu_callback, "_Center",     ("Center", zpa ) )
    zpa.add_menu_sep  ( images_menu )
    zpa.add_menu_item ( images_menu, menu_callback, "Clear All",  ("ClearAll", zpa ) )

  # Create a "Scales" menu
  (scales_menu, scales_item) = zpa.add_menu ( "_Scale" )
  if True: # An easy way to indent and still be legal Python
    zpa.add_menu_item ( scales_menu, menu_callback, "Scale _1",   ("Scale1", zpa ) )
    zpa.add_menu_sep  ( scales_menu )
    zpa.add_menu_item ( scales_menu, menu_callback, "Select",   ("ScaleSel", zpa ) )

  # Create a "Tile" menu
  (tile_menu, tile_item) = zpa.add_menu ( "Tile" )
  if True: # An easy way to indent and still be legal Python
    zpa.add_menu_item ( tile_menu, menu_callback, "Tile 0",    ("Tile_0", zpa ) )
    zpa.add_menu_item ( tile_menu, menu_callback, "Tile -1",   ("Tile_-1", zpa ) )
    zpa.add_menu_item ( tile_menu, menu_callback, "XPM 4-bit", ("Tile_-3", zpa ) )
    zpa.add_menu_item ( tile_menu, menu_callback, "XPM 6-bit", ("Tile_-4", zpa ) )
    zpa.add_menu_sep  ( tile_menu )
    zpa.add_menu_item ( tile_menu, menu_callback, "XPM Test",  ("Tile_-2", zpa ) )
    zpa.add_menu_sep  ( tile_menu )
    zpa.add_menu_item ( tile_menu, menu_callback, "Select",   ("TileSel", zpa ) )

  # Create a "Set" menu
  (set_menu, set_item) = zpa.add_menu ( "Set" )
  if True: # An easy way to indent and still be legal Python
    zpa.add_menu_item ( set_menu, menu_callback, "Debug 0",    ("Debug_0", zpa ) )
    zpa.add_menu_item ( set_menu, menu_callback, "Debug 40",   ("Debug_40", zpa ) )
    zpa.add_menu_item ( set_menu, menu_callback, "Debug 60",   ("Debug_60", zpa ) )
    zpa.add_menu_item ( set_menu, menu_callback, "Debug 100",  ("Debug_100", zpa ) )

  # Create a "Help" menu
  (help_menu, help_item) = zpa.add_menu ( "_Help" )
  if True: # An easy way to indent and still be legal Python
    zpa.add_menu_item ( help_menu, menu_callback, "Manual...",   ("Manual", zpa ) )
    zpa.add_menu_item ( help_menu, menu_callback, "Key commands...",   ("Key Commands", zpa ) )
    zpa.add_menu_item ( help_menu, menu_callback, "Mouse clicks...",   ("Mouse Clicks", zpa ) )

  # Append the menus to the menu bar itself
  menu_bar.append ( file_item )
  menu_bar.append ( images_item )
  menu_bar.append ( scales_item )
  menu_bar.append ( tile_item )
  menu_bar.append ( set_item )
  menu_bar.append ( help_item )

  # Show the menu bar itself (everything must be shown!!)
  menu_bar.show()

  # The zoom/pan area has its own drawing area (that it zooms and pans)
  drawing_area = zpa.get_drawing_area()

  # Add the zoom/pan area to the vertical box (becomes the main area)
  vbox.pack_start(drawing_area, True, True, 0)
  drawing_area.show()

  # The zoom/pan area doesn't draw anything, so add our custom expose callback
  drawing_area.connect ( "expose_event", expose_callback, zpa )

  # Set the events that the zoom/pan area must respond to
  #  Note that zooming and panning requires button press and pointer motion
  #  Other events can be set and handled by user code as well
  drawing_area.set_events ( gtk.gdk.EXPOSURE_MASK
                          | gtk.gdk.LEAVE_NOTIFY_MASK
                          | gtk.gdk.BUTTON_PRESS_MASK
                          | gtk.gdk.POINTER_MOTION_MASK
                          | gtk.gdk.POINTER_MOTION_HINT_MASK )

  # Create a horizontal box to hold application buttons
  hbox = gtk.HBox ( True, 0 )
  hbox.show()
  vbox.pack_start ( hbox, False, False, 0 )

  # Add some application specific buttons and their callbacks

  step_button = gtk.Button("Step")
  hbox.pack_start ( step_button, True, True, 0 )
  step_button.connect_object ( "clicked", step_callback, zpa )
  step_button.show()

  run_button = gtk.Button("Run")
  hbox.pack_start ( run_button, True, True, 0 )
  run_button.connect_object ( "clicked", run_callback, zpa )
  run_button.show()

  stop_button = gtk.Button("Stop")
  hbox.pack_start ( stop_button, True, True, 0 )
  stop_button.connect_object ( "clicked", stop_callback, zpa )
  stop_button.show()

  dump_button = gtk.Button("Dump")
  hbox.pack_start ( dump_button, True, True, 0 )
  dump_button.connect_object ( "clicked", dump_callback, zpa )
  dump_button.show()

  reset_button = gtk.Button("Reset")
  hbox.pack_start ( reset_button, True, True, 0 )
  reset_button.connect_object ( "clicked", reset_callback, zpa )
  reset_button.show()


  #zpa.user_data['image_frame'] = gtk.gdk.pixbuf_new_from_file ( "vj_097_shift_rot_skew_crop_4k4k_1.jpg" )
  zpa.user_data['image_frame'] = None

  # Show the main window
  window.show()

  zpa.set_cursor ( gtk.gdk.HAND2 )

  gtk.idle_add ( background_callback, zpa )

  # Turn control over to GTK to run everything from here onward.
  gtk.main()
  return 0


if __name__ == '__main__':
  main()
