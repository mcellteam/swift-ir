#!/usr/bin/env python2.7

import sys
import numpy as np
import traceback
try: import package.swiftir
except: import swiftir

# This is monotonic (0 to 100) with the amount of output:
debug_level = 100  # A larger value prints more stuff

# For now, always use the limited argument version
def print_debug ( level, p1=None, p2=None, p3=None, p4=None, p5=None ):
    # print_debug ( 1, "This is really important!!" )
    # print_debug ( 99, "This isn't very important." )
    global debug_level
    if level <= debug_level:
      if p1 == None:
        sys.stderr.write ( "" + '\n' )
      elif p2 == None:
        sys.stderr.write ( str(p1) + '\n' )
      elif p3 == None:
        sys.stderr.write ( str(p1) + str(p2) + '\n' )
      elif p4 == None:
        sys.stderr.write (str (p1) + str (p2) + str (p3) + '\n' )
      elif p5 == None:
        sys.stderr.write (str (p1) + str (p2) + str (p3) + str(p4) + '\n' )
      else:
        sys.stderr.write ( str(p1) + str(p2) + str(p3) + str(p4) + str(p5) + '\n' )

def print_debug_enter (level):
    if level <= debug_level:
        call_stack = inspect.stack()
        sys.stderr.write ( "Call Stack: " + str([stack_item.function for stack_item in call_stack][1:]) + '\n' )



def image_apply_affine(in_fn=None,out_fn=None,afm=None,rect=None,grayBorder=False):


        print_debug(12, "\nimage_apply_affine afm: " + str(afm))

        in_img = swiftir.loadImage(in_fn)
        print_debug(4, "\nTransforming " + str(in_fn) )
        print_debug(12, "  with:" )
        print_debug(12, "    afm = " + str(afm))
        print_debug(12, "    rect = " + str(rect))
        print_debug(12, "    grayBorder = " + str(grayBorder))
        out_img = swiftir.affineImage(afm, in_img, rect=rect, grayBorder=grayBorder) #0720 NOTE CALL TO swiftir.affineImage
        print_debug(4, "  saving transformed image as: " + str(out_fn))
        try:
            swiftir.saveImage(out_img, out_fn)
        except Exception:
            print('job_apply_affine.image_apply_affine | There was a problem saving the aligned images')
            print(traceback.format_exc())




def print_command_line_syntax ( args ):
  print_debug ( -1, "" )
  print_debug ( -1, 'Usage: %s [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' % (args[0]) )
  print_debug ( -1, 'Description:' )
  print_debug ( -1, '  Apply 2D affine matrix to input image file' )
  print_debug ( -1, '  with optional bounding rectangle and gray border.' )
  print_debug ( -1, '  Result is written to output image file.' )
  print_debug ( -1, 'Options:' )
  print_debug ( -1, '  -rect 0 0 100 100   : x_min y_min x_max y_max bounding rectangle' )
  print_debug ( -1, '  -gray               : output with gray border' )
  print_debug ( -1, '  -debug #            : # = debug level (0-100, larger numbers produce more output)' )
  print_debug ( -1, 'Arguments:' )
  print_debug ( -1, '  -afm 1 0 0 0 1 0    : the 2D affine matrix' )
  print_debug ( -1, '  in_file_name        : input image file name (opened for reading only)' )
  print_debug ( -1, '  out_file_name       : output image file name (opened for writing and overwritten)' )
  print_debug ( -1, "" )



if (__name__ == '__main__'):

  if (len(sys.argv)<4):
    print_command_line_syntax (sys.argv)
    exit(1)

  in_fn = sys.argv[-2]
  out_fn = sys.argv[-1]

  rect = None
  grayBorder = False
  debug_level = 10

  # Scan arguments (excluding program name and last 2 file names)
  i = 1
  while (i < len(sys.argv)-2):
    print_debug (10, "Processing option " + sys.argv[i])
    if sys.argv[i] == '-afm':
      afm_list = []
      # Extend afm_list using the next 6 args
      for n in range(6):
        i += 1  # Increment to get the argument
        afm_list.extend([float(sys.argv [i])])
      afm = np.array(afm_list,dtype='float64').reshape((-1,3))
    elif sys.argv [i] == '-rect':
      rect_list = []
      # Extend rect_list using the next 4 args
      for n in range(4):
        i += 1  # Increment to get the argument
        rect_list.extend([int(sys.argv [i])])
      rect = np.array(rect_list,dtype='int')
    elif sys.argv[i] == '-gray':
      grayBorder = True
      # No need to increment i because no additional arguments were taken
    elif sys.argv [i] == '-debug':
      i += 1  # Increment to get the argument
      debug_level = int (sys.argv [i])
    else:
      print_debug (-1, "\nImproper argument list: " + str(argv) + "\n")
      print_command_line_syntax ( sys.argv )
      exit(1)
    i += 1  # Increment to get the next option

  image_apply_affine(in_fn=in_fn, out_fn=out_fn, afm=afm, rect=rect, grayBorder=grayBorder)

  sys.stdout.close()
  sys.stderr.close()

