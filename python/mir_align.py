#!/usr/bin/env python2.7

import os
import sys
import math
import numpy as np
import cv2

import subprocess as sp


debug_level = 10

def print_debug ( level, str ):
  global debug_level
  if level <= debug_level:
    print ( str )

global_swiftir_mode = 'python'   # Either 'python' or 'c'


def run_command(cmd, arg_list=None, cmd_input=None):

  print_debug ( 10, "\n================== Run Command ==================" )
  cmd_arg_list = [ cmd ]
  if arg_list != None:
    cmd_arg_list = [ a for a in arg_list ]
    cmd_arg_list.insert ( 0, cmd )
  print_debug ( 10, "  Running command: " + str(cmd_arg_list) )
  print_debug ( 20, "   Passing Data\n==========================\n" + str(cmd_input) + "==========================\n" )
  cmd_proc = sp.Popen(cmd_arg_list,stdin=sp.PIPE,stdout=sp.PIPE,stderr=sp.PIPE,universal_newlines=True)
  cmd_stdout, cmd_stderr = cmd_proc.communicate(cmd_input)

  # Note: decode bytes if universal_newlines=False in Popen
  #cmd_stdout = cmd_stdout.decode('utf-8')
  #cmd_stderr = cmd_stderr.decode('utf-8')
  print_debug ( 20, "Command output: \n\n" + cmd_stdout + "==========================\n" )
  print_debug ( 30, "Command error: \n\n"  + cmd_stderr + "==========================\n" )

  print_debug ( 10, "=================================================\n" )

  return ( { 'out': cmd_stdout, 'err': cmd_stderr } )



def main(args):
  print_debug ( 10, "Running " + __file__ + ".__main__()" )

  f1 = None
  f2 = None
  N = 5

  if len(args) <= 2:

    print ( "Usage: python " + __file__ + " image1 image2 [N]" )

  else:

    # Process and remove the fixed positional arguments
    args = args[1:]  # Shift out this file name (argv[0])
    if (len(args) > 0) and (not args[0].startswith('-')):
      f1 = args[0]
      args = args[1:]  # Shift out the first file name argument
      if (len(args) > 0) and (not args[0].startswith('-')):
        f2 = args[0]
        args = args[1:]  # Shift out the second file name argument
        if (len(args) > 0) and (not args[0].startswith('-')):
          N = int(args[0])
          args = args[1:]  # Shift out the destination argument

    print ( "Aligning " + f2 + " to " + f1 + " using a grid of " + str(N) + "x" + str(N) )

    base = cv2.imread ( f1, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE )
    move = cv2.imread ( f2, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE )
    (h,w) = base.shape

    # Calculate the points list and triangles

    R = N
    C = N
    points = []
    for yi in range(R):
      ypre = yi * h / (R-1)
      ypost = ypre + 0
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

    ww = 256
    ww = int ( 2 * ((h+w)/2) / N )
    print ( "\n=========== Swim Script ============\n" + str(swim_script) + "============================\n" )
    o = run_command ( "swim", arg_list=[str(ww)], cmd_input=swim_script )
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

    mir_script += 'W mir_align_out.jpg' + os.linesep

    #print ( mir_script )

    run_command ( "mir", arg_list=[], cmd_input=mir_script )

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})


if __name__=='__main__':
  main ( sys.argv )

