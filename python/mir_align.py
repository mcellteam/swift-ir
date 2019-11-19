#!/usr/bin/env python2.7

import numpy as np
import os

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


import sys

mir_script = """F vj_097_shift_rot_skew_crop_4k4k_1.jpg
10 10 10 10
10 3990 10 3990
3990 10 3990 10
3000 3000 3990 3990
T
0 1 3
3 2 0
W vj_mod.jpg"""

if __name__=='__main__':
  print_debug ( 10, "Running " + __file__ + ".__main__()" )
  run_command ( "mir", arg_list=[], cmd_input=mir_script )


