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


  if len(sys.argv) > 1:
    fn = sys.argv[1]
    img = cv2.imread ( fn, cv2.IMREAD_ANYDEPTH + cv2.IMREAD_GRAYSCALE )
    (h,w) = img.shape

    # Make a mir script
    mir_script  = ''
    mir_script += 'F ' + fn + os.linesep
    R = 50
    C = 50
    for yi in range(R):
      ypre = yi * h / (R-1)
      ypost = ypre + 0
      for xi in range(C):
        xpre = xi * w / (C-1)
        xpost = xpre + ((w/100) * math.sin(5*math.pi*yi/R))
        mir_script += "%d %d %d %d" % (xpost, ypost, xpre, ypre) + os.linesep
    mir_script += 'T' + os.linesep

    for yi in range(R-1):
      yleft = yi * C
      for xi in range(C-1):
        mir_script += "%d %d %d" % (yleft+xi, yleft+C+xi, yleft+xi+1) + os.linesep
        mir_script += "%d %d %d" % (yleft+xi+C+1, yleft+xi+1,yleft+C+xi) + os.linesep
    mir_script += 'W mir_align_out.jpg' + os.linesep

    print ( mir_script )

    #exit()

    #__import__('code').interact(local={k: v for ns in (globals(), locals()) for k, v in ns.items()})

  run_command ( "mir", arg_list=[], cmd_input=mir_script )


if __name__=='__main__':
  main ( sys.argv )

