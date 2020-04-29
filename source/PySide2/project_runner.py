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
import task_wrapper
import pyswift_tui
import alignem

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


class project_runner:
  ''' Run an alignment project by splitting it up by scales and/or layers '''
  # The project_runner starts with a Full Data Model (FDM)
  # The project_runner may run in either serial or parallel mode
  # When running in serial mode, the project_runner calls run_json_project directly
  # When running in parallel mode:
  #   The project_runner writes the FDM to a temporary file to be read by the worker tasks
  #   The project_runner breaks up the alignment layers into specific jobs and starts a worker (pyswift_tui) for each job
  #   Each worker will see the temporary data model file and get command line parameters about which part(s) it must complete
  #   The project_runner will collect the alignment data from each pyswift_tui run and integrate it into the "master" data model
  def __init__ ( self, project=None, alignment_option='init_affine', use_scale=0, swiftir_code_mode='python', start_layer=0, num_layers=-1, run_parallel=False ):

    print ( "\n\n\nCreating a project runner...\n\n\n")
    if use_scale <= 0:
      print ( "Error: project_runner must be given an explicit scale")
      return
    self.project = copy.deepcopy ( project )
    self.alignment_option = alignment_option
    self.use_scale = use_scale
    self.swiftir_code_mode = swiftir_code_mode
    self.start_layer = start_layer
    self.num_layers = num_layers
    self.run_parallel = run_parallel
    self.task_queue = None
    self.updated_model = None
    self.need_to_write_json = None


  def start ( self ):
    print ( "Starting Jobs" )

    #__import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })

    scale_key = "scale_%d" % self.use_scale
    alstack = self.project['data']['scales'][scale_key]['alignment_stack']

    if self.run_parallel:

      # Run the project as a series of jobs

      # Write the entire project as a single JSON file with a unique stable name for this run

      f = tempfile.NamedTemporaryFile (prefix="temp_proj_", suffix=".json", dir=self.project['data']['destination_path'], delete=False)
      run_project_name = f.name
      f.close()
      print ("Temp file is: " + str (f.name))
      f = open ( run_project_name, 'w')
      jde = json.JSONEncoder (indent=2, separators=(",", ": "), sort_keys=True)
      proj_json = jde.encode (self.project)
      f.write (proj_json)
      f.close ()

      # Prepare the task queue

      task_queue.debug_level = alignem.debug_level
      task_wrapper.debug_level = alignem.debug_level

      self.task_queue = task_queue.TaskQueue(sys.executable)
      self.task_queue.start ( psutil.cpu_count(logical=False) )
      self.task_queue.notify = True

      for layer in alstack:
        lnum = alstack.index(layer)
        print ( "Starting a task for layer " + str(lnum) )
        self.task_queue.add_task ( cmd=sys.executable,
                                   args=['single_alignment_job.py',
                                          str(run_project_name),
                                          str(self.alignment_option),
                                          str(self.use_scale),
                                          str(self.swiftir_code_mode),
                                          str(lnum),
                                          str(1)
                                          ],
                                   wd='.' )
                                   # wd=self.project['data']['destination_path'] )

      self.task_queue.work_q.join()

      print ("Tasks completed with these arguments")
      for k in self.task_queue.task_dict.keys():
        print ( '  ' + str(self.task_queue.task_dict[k]['args']) + " " + str(self.task_queue.task_dict[k]['status']) )

      # Sort the tasks by layers rather than by process IDs
      task_dict_by_start_layer = {}
      for k in self.task_queue.task_dict.keys():
        t = self.task_queue.task_dict[k]
        task_dict_by_start_layer[int(t['args'][5])] = t

      tasks_by_start_layer = []
      for k in sorted(task_dict_by_start_layer.keys()):
        tasks_by_start_layer.append ( task_dict_by_start_layer[k] )

      print ("Tasks sorted by layer numbers")
      for l in tasks_by_start_layer:
        print ( '  ' + str(l['args']) + '  ' + str(l['status']) )

      # Integrate the output from each task into a new combined data model

      self.updated_model = copy.deepcopy ( self.project )

      cur_scale_new_key = self.updated_model['data']['current_scale']
      if self.use_scale > 0:
        cur_scale_new_key = 'scale_' + str(self.use_scale)

      for tnum in range(len(tasks_by_start_layer)):

        parts = tasks_by_start_layer[tnum]['stdout'].split('---JSON-DELIMITER---')
        dm_text = None
        for p in parts:
          ps = p.strip()
          if ps.startswith('{') and ps.endswith('}'):
            dm_text = p
        if dm_text != None:
          results_dict = json.loads(dm_text)
          fdm_new = results_dict['data_model']

          # Get the same scale from both the old and new data models
          cur_scale_new = fdm_new['data']['scales'][cur_scale_new_key]
          cur_scale_old = self.updated_model['data']['scales'][cur_scale_new_key]

          al_stack_old = cur_scale_old['alignment_stack']
          al_stack_new = cur_scale_new['alignment_stack']

          lnum = int(tasks_by_start_layer[tnum]['args'][5]) # Note that this may differ from tnum!!

          al_stack_old[lnum] = al_stack_new[lnum]

          self.need_to_write_json = results_dict['need_to_write_json']  # It's not clear how this should be used (many to one)

      # Propagate the AFMs to generate and appropriate CFM at each layer
      pyswift_tui.SetStackCafm ( self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'] )

      # Finally generate the images with a parallel run of image_apply_affine.py

      for tnum in range(len(tasks_by_start_layer)):
        tdata = tasks_by_start_layer[tnum]
        layer_index = int(tdata['args'][5])  # Note the hard-coded index of 5 here is not the best way to go!!
        layer = self.updated_model['data']['scales'][cur_scale_new_key]['alignment_stack'][layer_index]

        base_name = layer['images']['base']['filename']
        ref_name = layer['images']['ref']['filename']

        al_path,fn = os.path.split(base_name)
        al_name = os.path.join(os.path.split(al_path)[0],'img_aligned',fn)

        cafm = layer['align_to_ref_method']['method_results']['cumulative_afm']

        print_debug ( -1, 'Run processes for: python image_align_affine.py [ options ] -afm 1 0 0 0 1 0  in_file_name out_file_name' )

        self.task_queue.add_task ( cmd=sys.executable,
                                   args=[ 'image_align_affine.py',
                                          '-afm',
                                          str(cafm[0][0]),
                                          str(cafm[0][1]),
                                          str(cafm[0][2]),
                                          str(cafm[1][0]),
                                          str(cafm[1][1]),
                                          str(cafm[1][2]),
                                          base_name,
                                          al_name
                                          ],
                                   wd='.' )
                                   # wd=self.project['data']['destination_path'] )

      # __import__ ('code').interact (local={ k: v for ns in (globals (), locals ()) for k, v in ns.items () })

      self.task_queue.work_q.join()

    else:

      # Run the project directly as one serial model
      print ( "Running the project as one serial model")
      self.updated_model, self.need_to_write_json = pyswift_tui.run_json_project (
                                             project = self.project,
                                             alignment_option = self.alignment_option,
                                             use_scale = self.use_scale,
                                             swiftir_code_mode = self.swiftir_code_mode,
                                             start_layer = self.start_layer,
                                             num_layers = self.num_layers )


  def join ( self ):
    print ( "Waiting for Jobs to finish" )

  def get_updated_data_model ( self ):
    print ( "Returning the updated data model" )
    return self.updated_model

if (__name__ == '__main__'):
  print ("Align Task Manager run as main ... not sure what this should do.")

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