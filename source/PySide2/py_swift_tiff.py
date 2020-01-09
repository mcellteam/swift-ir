import sys
import struct
import argparse

# Functions to convert between Python values and C structs.
# Python bytes objects are used to hold the data representing the C struct
# and also as format strings (explained below) to describe the layout of data
# in the C struct.

# The optional first format char indicates byte order, size and alignment:
#   @: native order, size & alignment (default)
#   =: native order, std. size & alignment
#   <: little-endian, std. size & alignment
#   >: big-endian, std. size & alignment
#   !: same as >

# The remaining chars indicate types of args and must match exactly;
# these can be preceded by a decimal repeat count:
#   x: pad byte (no data);
#   c: char;\
#   b: signed byte;
#   B: unsigned byte;
#   ?: _Bool (requires C99; if not available, char is used instead)
#   h:short;
#   H:unsigned short;
#   i:int;
#   I:unsigned int;
#   l:long;
#   L:unsigned long;
#   f:float;
#   d:double.
# Special cases (preceding decimal count indicates length):
#   s:string (array of char); p: pascal string (with count byte).
# Special cases (only available in native format):
#   n:ssize_t; N:size_t;
#   P:an integer type that is wide enough to hold a pointer.
# Special case (not in native mode unless 'long long' in platform C):
#   q:long long; Q:unsigned long long
# Whitespace between formats is ignored.

# TIFF Specification

# Value/Offset
#  To save time and space the Value Offset contains the Value instead
#  of pointing to the Value if and only if the Value fits into 4 bytes.
#  If the Value is shorter than 4 bytes, it is left-justified within
#  the 4-byte Value Offset, i.e., stored in the lower-numbered bytes.
#  Whether the Value fits within 4 bytes is determined by the Type and
#  Count of the field.

def is_immediate ( tagtuple ):
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


def str_from_tag ( t ):
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

def dump_tiff ( fname ):
  if sys.version_info.major != 3:
    print ( "This program must be run with Python 3 because it reads bytes." )
    exit ( 0 )

  # fname = 'TIFF_RGBM.tif'
  #if len(sys.argv) > 1:
  #  fname = sys.argv[1]

  print ( "Reading tif file named " + str(fname) + "\n" )

  fdata = None
  flen = None
  with open ( fname, mode='rb' ) as f:
    fdata = f.read()
    flen = f.seek(0,2)

  print ( "File length = " + str(flen) )
  bigend = False
  send = '<'

  if (fdata[0] == 0x49) and (fdata[1] == 0x49):
    # This is "Intel" format
    bigend = False
    send = '<'
    print ( "This file is in Intel format (little endian)" )
    if fdata[0:4] != bytes([0x49, 0x49, 0x2a, 0x00]):
      print ( "Error: bytes did not match: " + str(fdata[0:4]) )
      exit ( 0 )

  elif (fdata[0] == 0x4d) and (fdata[1] == 0x4d):
    # This is "Motorola" format
    bigend = True
    send = '>'
    print ( "This file is in Motorola format (big endian)" )
    if fdata[0:4] != bytes([0x4d, 0x4d, 0x00, 0x2a]):
      print ( "Error: bytes did not match: " + str(fdata[0:4]) )
      exit ( 0 )

  else:
    # This is not likely to be a TIFF file
    print ( "Error: This does not appear to be a TIFF file: " + str(fdata[0:4]) )
    exit ( 0 )

  tiffHeader = struct.unpack_from ( send+'BBHL', fdata[0:8], offset=0 )
  version = tiffHeader[2]
  offset = tiffHeader[3]
  print ( "tiffHeader = " + str(tiffHeader) )
  print ( "tiff version = " + str(version) + ", offset = " + str(offset) )

  class tag_record:
    def __init__ ( self, tag, tagtype, tagcount, tagvalue ):
      self.tag = tag
      self.tagtype = tagtype
      self.tagcount = tagcount
      self.tagvalue = tagvalue
    def __repr__ ( self ):
      return ( "TR: " + str(self.tag) + ", " + str(self.tagtype) + ", " + str(self.tagcount) + ", " + str(self.tagvalue) )

  print ( "\n" )
  print ( 120*"=" )
  print ( "\n" )

  dir_record_list = []
  tag_record_list = []

  dir_num = 1

  while offset > 0:
    numDirEntries = struct.unpack_from ( send+'H', fdata, offset=offset )
    offset += 2
    print ( "Directory " + str(dir_num) + " has NumDirEntries = " + str(numDirEntries[0]) )
    dir_num += 1
    # Read the tags
    for tagnum in range(numDirEntries[0]):
      tagtuple = struct.unpack_from ( send+'HHLL', fdata, offset=offset )
      tag = tagtuple[0]
      tagtype = tagtuple[1]
      tagcount = tagtuple[2]
      tagvalue = tagtuple[3]
      tag_record_list.append ( tag_record ( tag, tagtype, tagcount, tagvalue ) )
      offset += 12
      tagstr = str_from_tag ( tagtuple )
      if tagstr.endswith ( 'ASCII' ):
        ascii_str = ":  \""
        for i in range(tagcount):
          try:
            ascii_str += str(struct.unpack_from ( send+'s', fdata, offset=tagvalue+i )[0].decode('utf-8'))
          except:
            ascii_str += '?'
            print ( "     Decoding error for " + str(struct.unpack_from ( send+'s', fdata, offset=tagvalue+i )[0]) + " in following tag:" )
        if len(ascii_str) > 60:
          ascii_str = ascii_str[0:60]
        ascii_str = ascii_str.replace ( "\n", " " )
        ascii_str = ascii_str.replace ( "\r", " " )
        tagstr += ascii_str + "\""
      print ( "  Tag = " + str(tagtuple) + " = " + tagstr )
    dir_record_list.append ( tag_record_list )
    tag_record_list = []
    nextIFDOffset = struct.unpack_from ( send+'L', fdata, offset=offset )
    offset = nextIFDOffset[0]
    print ( "\n" )

  print ( "\n\n" )
  print ( 120*"=" )
  print ( "\n\n" )

  dir_num = 1
  for dir_record in dir_record_list:
    print ( "Directory " + str(dir_num) + ":\n" )
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
    for tag_record in dir_record:
      print ( "  New tag: " + str(tag_record) )
      if tag_record.tag == 256:
        w = tag_record.tagvalue
        print ( "    Width: " + str(tag_record.tagvalue) )
      if tag_record.tag == 257:
        h = tag_record.tagvalue
        print ( "    Height: " + str(tag_record.tagvalue) )
      if tag_record.tag == 258:
        bps = tag_record.tagvalue
        print ( "    Bits/Samp: " + str(tag_record.tagvalue) )
        if bps != 8:
          print ( "Can't handle files with " + str(bps) + " bits per sample" )
          exit ( 0 )
      if tag_record.tag == 322:
        tw = tag_record.tagvalue
        print ( "    TileWidth: " + str(tag_record.tagvalue) )
      if tag_record.tag == 323:
        tl = tag_record.tagvalue
        print ( "    TileLength: " + str(tag_record.tagvalue) )
      if tag_record.tag == 324:
        to = tag_record.tagvalue
        print ( "    TileOffsets: " + str(tag_record.tagvalue) )
        offsets = struct.unpack_from ( send+(tag_record.tagcount*"L"), fdata, offset=tag_record.tagvalue )
        print ( "       " + str(offsets) )
      if tag_record.tag == 325:
        tc = tag_record.tagvalue
        print ( "    TileByteCounts: " + str(tag_record.tagvalue) )
        counts = struct.unpack_from ( send+(tag_record.tagcount*"L"), fdata, offset=tag_record.tagvalue )
        print ( "       " + str(counts) )

    if not (None in (bps, w, h, tw, tl, to, tc)):
      print ( "\nFound a block of tiles:\n" )
      for i in range(len(offsets)):
        offset = offsets[i]
        count = counts[i]
        try:
          data = struct.unpack_from ( send+"BBBB", fdata, offset=offset )
        except:
          exi = sys.exc_info()
          print ( "Exception type = " + str(exi[0]) )
          print ( "Exception value = " + str(exi[1]) )
          print ( "Exception trace = " + str(exi[2]) )
          __import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})
        #print ( "Read data " + str(data) + " from " + str(offset) )
        #print ( "" )
    '''
    if not (None in (bps, w, h, tw, tl, to, tc)):
      print ( "\nFound a block of tiles:\n" )
      for i in range(len(offsets)):
        offset = offsets[i]
        count = counts[i]
        data = struct.unpack_from ( send+(count*"B"), fdata, offset=offset )
        for r in range(tl):
          print ( str ( [ data[(r*tw)+d] for d in range(tw) ] ) )
        print ( "" )
    '''

    # offset = 0 ############ Force a stop


  print ( "\n\n" )

if __name__ == "__main__":
  options = argparse.ArgumentParser()
  options.add_argument("-f", "--file", type=str, required=True)
  args = options.parse_args()
  #__import__('code').interact(local=locals())
  fname = args.file
  dump_tiff ( fname )


