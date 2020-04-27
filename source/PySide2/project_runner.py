#!/usr/bin/env python2.7

import sys
import os
import json
import copy
import errno
import inspect
import argparse
import tempfile
import psutil
import numpy as np
import scipy.stats as sps
import matplotlib.pyplot as plt
import swiftir
import align_swiftir
import task_queue
import pyswift_tui

# This is monotonic (0 to 100) with the amount of output:
debug_level = 50  # A larger value prints more stuff

# Using the Python version does not work because the Python 3 code can't
# even be parsed by Python2. It could be dynamically compiled, or use the
# alternate syntax, but that's more work than it's worth for now.
if sys.version_info >= (3, 0):
    # print ( "Python 3: Supports arbitrary arguments via print")
    #def print_debug ( level, *ds ):
    #  # print_debug ( 1, "This is really important!!" )
    #  # print_debug ( 99, "This isn't very important." )
    #  global debug_level
    #  if level <= debug_level:
    #    print ( *ds )
    pass
else:
    # print ("Python 2: Use default parameters for limited support of arbitrary arguments via print")
    pass

# For now, always use the limited argument version
def print_debug ( level, p1=None, p2=None, p3=None, p4=None, p5=None ):
    # print_debug ( 1, "This is really important!!" )
    # print_debug ( 99, "This isn't very important." )
    global debug_level
    if level <= debug_level:
      if p1 == None:
        print ( "" )
      elif p2 == None:
        print ( str(p1) )
      elif p3 == None:
        print ( str(p1) + str(p2) )
      elif p4 == None:
        print (str (p1) + str (p2) + str (p3))
      elif p5 == None:
        print (str (p1) + str (p2) + str (p3) + str(p4))
      else:
        print ( str(p1) + str(p2) + str(p3) + str(p4) + str(p5) )

def print_debug_enter (level):
    if level <= debug_level:
        call_stack = inspect.stack()
        print ( "Call Stack: " + str([stack_item.function for stack_item in call_stack][1:]) )


class alignment_task_manager:
  ''' Run an alignment project by splitting it up by scales and/or layers '''
  def __init__ ( self, project=None, alignment_option='init_affine', use_scale=0, swiftir_code_mode='python', start_layer=0, num_layers=-1 ):

    if use_scale <= 0:
      print ( "Error: alignment_task_manager must be given an explicit scale")
      return

    self.project = copy.deepcopy ( project )
    self.alignment_option = alignment_option
    self.use_scale = use_scale
    self.swifir_code_mode = swiftir_code_mode
    self.start_layer = start_layer
    self.num_layers = num_layers

    self.task_queue.debug_level = alignem.debug_level
    self.task_wrapper.debug_level = alignem.debug_level

    self.task_queue = task_queue.TaskQueue(sys.executable)
    self.task_queue.start ( psutil.cpu_count(logical=False) )
    self.task_queue.notify = True

    # Write the entire project as a single JSON file with a unique stable name for this run

    # TODO: The "dir" here should be the destination path resolved from the project file:
    f = tempfile.NamedTemporaryFile (prefix="temp_proj_", suffix=".json", dir=".", delete=False)
    print ("Temp file is: " + str (f.name))
    jde = json.JSONEncoder (indent=2, separators=(",", ": "), sort_keys=True)
    proj_json = jde.encode (proj_copy)
    f.write (proj_json)
    f.close ()

    scale_key = "scale_%d" % use_scale
    alstack = self.project['data']['scales'][scale_key]['alignment_stack']
    for layer in alstack:
      self.task_queue.add_task (cmd=sys.executable,
                                args=['pyswift_tui.py',
                                      '-code', swiftir_code_mode,
                                      '-scale', str(use_scale),
                                      '-start', '0',
                                      '-count', '1',
                                      '-alignment_option', str (abs_file_name), str (outfile_name)], wd='.')
    '''
    # Command line interface to pyswift_tui:

    def print_command_line_syntax ( args ):
      print_debug ( -1, "" )
      print_debug ( -1, 'Usage: %s [ options ] inproject.json outproject.json' % (args[0]) )
      print_debug ( -1, 'Description:' )
      print_debug ( -1, '  Open swiftir project file and perform alignment operations.' )
      print_debug ( -1, '  Result is written to output project file.' )
      print_debug ( -1, 'Options:' )
      print_debug ( -1, '  -code m             : m = c | python' )
      print_debug ( -1, '  -scale #            : # = first layer number (starting at 0), defaults to 0' )
      print_debug ( -1, '  -start #            : # = first layer number (starting at 0), defaults to 0' )
      print_debug ( -1, '  -count #            : # = number of layers (-1 for all remaining), defaults to -1' )
      print_debug ( -1, '  -debug #            : # = debug level (0-100, larger numbers produce more output)' )
      print_debug ( -1, '  -alignment_option o : o = init_affine | refine_affine | apply_affine' )
      print_debug ( -1, '  -master             : Run as master process .. generate sub-data-models and delegate' )
      print_debug ( -1, '  -worker             : Run as worker process .. work only on this particular data model' )
      print_debug ( -1, 'Arguments:' )
      print_debug ( -1, '  inproject.json      : input project file name (opened for reading only)' )
      print_debug ( -1, '  outproject.json     : output project file name (opened for writing and overwritten)' )
      print_debug ( -1, "" )
    '''

if (__name__ == '__main__'):
  print ("Align Task Manager run as main ... not sure what this should do.")

  import psutil
  from argparse import ArgumentParser
  import time

  my_q = task_queue.TaskQueue (sys.executable)

  cpus = 3

  my_q.start (cpus)
  my_q.notify = True

  begin = time.time ()

  wd = '.'

  my_q.add_task (cmd='cp foo.txt foo_1.txt', wd=wd)
  my_q.add_task (cmd='cp foo.txt foo_2.txt', wd=wd)
  my_q.add_task (cmd='cp foo.txt foo_3.txt', wd=wd)
  my_q.add_task (cmd='cp foo.txt foo_4.txt', wd=wd)
  my_q.add_task (cmd='pwd', wd=wd)
  my_q.add_task (cmd='ls', args='.', wd=wd)
  my_q.add_task (cmd='echo', args='Hello World!!!', wd=wd)

  time.sleep (2.)

  pids = list (my_q.task_dict.keys ())
  pids.sort ()

  my_q.work_q.join ()

  if debug_level > 4: sys.stdout.write ('\n\nTook {0:0.2f} seconds.\n\n'.format (time.time () - begin))

'''

  if (len(sys.argv)<3):
    print_command_line_syntax (sys.argv)
    exit(1)

  proj_ifn = sys.argv[-2]
  proj_ofn = sys.argv[-1]

  use_scale = 0
  alignment_option = 'refine_affine'
  scale_tbd = 0
  finest_scale_done = 0
  swiftir_code_mode = 'python'
  start_layer = 0
  num_layers = -1
  run_as_master = False
  run_as_worker = False
  alone = False

  # Scan arguments (excluding program name and last 2 file names)
  i = 1
  while (i < len(sys.argv)-2):
    print ( "Processing option " + sys.argv[i])
    if sys.argv[i] == '-master':
      run_as_master = True
      # No need to increment i because no additional arguments were taken
    elif sys.argv [i] == '-worker':
      run_as_worker = True
      alone = True
      # No need to increment i because no additional arguments were taken
    elif sys.argv[i] == '-scale':
      i += 1  # Increment to get the argument
      use_scale = int(sys.argv[i])
    elif sys.argv[i] == '-code':
      i += 1  # Increment to get the argument
      # align_swiftir.global_swiftir_mode = str(sys.argv[i+1])
      swiftir_code_mode = str(sys.argv[i])
    elif sys.argv [i] == '-alignment_option':
      i += 1  # Increment to get the argument
      alignment_option = sys.argv [i]
    elif sys.argv [i] == '-start':
      i += 1  # Increment to get the argument
      start_layer = int(sys.argv [i])
    elif sys.argv [i] == '-count':
      i += 1  # Increment to get the argument
      num_layers = int (sys.argv [i])
    elif sys.argv [i] == '-debug':
      i += 1  # Increment to get the argument
      debug_level = int (sys.argv [i])
    else:
      print ( "\nImproper argument list: " + str(argv) + "\n")
      print_command_line_syntax ( sys.argv )
      exit(1)
    i += 1  # Increment to get the next option

  #fp = open('/m2scratch/bartol/swift-ir_tests/LM9R5CA1_project.json','r')
  fp = open(proj_ifn,'r')

  d = json.load(fp)
  need_to_write_json = False

  if run_as_worker:

    # This task was called to just process one layer
    print_debug ( 1, "Running as a worker for just one layer with PID=" + str(os.getpid()) )
    # Chop up the JSON project so that the only layer is the one requested
    for scale_key in d['data']['scales'].keys():
      scale = d['data']['scales'][scale_key]
      # Set the entire stack equal to the single layer that needs to be aligned (including both ref and base)
      scale['alignment_stack'] = [ scale['alignment_stack'][start_layer] ]

    # Call run_json_project with the partial data model and the "alone" flag set to True
    d, need_to_write_json = run_json_project ( project=d,
                                               alignment_option=alignment_option,
                                               use_scale=use_scale,
                                               swiftir_code_mode=swiftir_code_mode,
                                               start_layer=start_layer,
                                               num_layers=num_layers,
                                               alone=True)

    # When run as a worker, always return the data model to the master on stdout
    print ("NEED TO RETURN DATA MODEL TO MASTER from PID=" + str(os.getpid()))

  elif run_as_master:

    print_debug ( -1, "Error: The \"run_as_master\" flag should not be used in the current design." )
    exit(99)

  else:

    # This task was called to process the entire stack in serial mode
    print_debug ( 1, "Running in serial mode with PID=" + str(os.getpid()) )

    align_swiftir.debug_level = debug_level
    print_debug ( 20, "Before RJP: " + str( [ d['data']['current_scale'], alignment_option, use_scale, swiftir_code_mode, start_layer, num_layers, alone ] ) )


    d, need_to_write_json = run_json_project ( project=d,
                                               alignment_option=alignment_option,
                                               use_scale=use_scale,
                                               swiftir_code_mode=swiftir_code_mode,
                                               start_layer=start_layer,
                                               num_layers=num_layers,
                                               alone=alone)
    if need_to_write_json:

      # Write out updated json project file
      print_debug(50,"Writing project to file: ", proj_ofn)
      ofp = open(proj_ofn,'w')
      json.dump(d,ofp, sort_keys=True, indent=2, separators=(',', ': '))
'''