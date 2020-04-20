#!/usr/bin/env python3

import sys
import os
if sys.version_info.major == 3:
  from queue import Queue, Empty
else:
  from Queue import Queue, Empty
import threading
import subprocess as sp
import time

'''
#################################

First useful attempt at a Set of classes for managing processes via a Queue and ThreadWorkers
The goal is to manage some number of  tasks to be run concurrently by N threadworkers
and capture the stdout and stderr of each task.

Two main classes are defined:

1) The OutputQueue class allows the management of the stdout and stderr streams of individual tasks wrapped by task_wrapper.py
   a) NB: task_wrapper.py is a python script that waits for the command string and argument string to be sent on stdin.

2) The TaskQueue class manages all the tasks and threadworkers that process the tasks.
   a) each task is a dictionary containing:
      i) a Popen object for a task_wrapper.py process which waits in idle for the command and args to be sent to its stdin
     ii) all the other task attributes

#################################
'''


# class for managing stdout and stderr streams of a running task wrapped by task_wrapper.py
class OutputQueue:
  def __init__(self):
    self.out_q = Queue(maxsize=0)
    self.err_q = Queue(maxsize=0)

  # Process stdout or stderr pipes of running process (e.g. typically capture the output and copy onto a queue or append to list)
  def read_output(self, pipe, funcs):
    for line in iter(pipe.readline, b''):
      line = line.decode('utf-8')
      for func in funcs:
        func(line)  # execute the func: possible values: 1) the Queue.put function; 2) the list.append function
    pipe.close()

  # Get strings found in the out_q or err_q and write to sys.stdout or sys.stderr
  def write_output(self, get, pipe, output_list=None):
    for line in iter(get, None):
      pipe.write(line)
      pipe.flush()
      if output_list != None:
        output_list.append ( line )

  # Recursive function to flatten a list of lists into a single list
  def flatten_list ( self, l, f ):
      for i in l:
          if type(i) == type([]):
              self.flatten_list(i, f)
          else:
              print ( " item: " + str(i) )
              f.append ( i )
      print ( "flattened so far: " + str(f) )


  # In passthrough mode, set up threadworkers and queues to manage stdout and stderr of task and send command string and args to task_wrapper.py process
  # Otherwise just do proc.communicate() and capture stdout and stderr upon command completion (possibly broken functionality?)
  def run_proc(self, proc, arg_in=None, passthrough=True, output_list=None):

    if passthrough:

      outs, errs = [], []

      stdout_reader_thread = threading.Thread(
          target=self.read_output, args=(proc.stdout, [self.out_q.put, outs.append])
          )

      stderr_reader_thread = threading.Thread(
          target=self.read_output, args=(proc.stderr, [self.err_q.put, errs.append])
          )

      stdout_writer_thread = threading.Thread(
          target=self.write_output, args=(self.out_q.get, sys.stdout, output_list)
          )

      stderr_writer_thread = threading.Thread(
          target=self.write_output, args=(self.err_q.get, sys.stderr, output_list)
          )

      for t in (stdout_reader_thread, stderr_reader_thread, stdout_writer_thread, stderr_writer_thread):
        t.daemon = True
        t.start()

      if arg_in:
        sys.stdout.write('run_proc in task_queue.py with arg_in = ' + str(arg_in) + '\n')
        sys.stdout.write('run_proc in task_queue.py with args:\n')
        for arg in arg_in:
          char_stream = ""
          if type(arg) == type([]):
            # Convert the list to quoted argument format
            flat_arg = []
            self.flatten_list ( arg, flat_arg );
            for a in flat_arg:
              char_stream += '"' + a + '" '
            if len(char_stream) > 0:
              char_stream = char_stream[0:-1]
            # Convert the list to a string (for now) by joining
            # char_stream = ' '.join ( arg )
          else:
            # Use previous string format
            char_stream = arg
          sys.stdout.write('  arg: ' + str(char_stream) + '\n')
#          sys.stdout.write('run_proc sending: {0}\n'.format(arg).encode().decode())
          proc.stdin.write('{0}\n'.format(char_stream).encode())
          proc.stdin.flush()
      proc.wait()

      for t in (stdout_reader_thread, stderr_reader_thread):
        t.join()

      self.out_q.put(None)
      self.err_q.put(None)

      for t in (stdout_writer_thread, stderr_writer_thread):
        t.join()

      outs = ' '.join(outs)
      errs = ' '.join(errs)

    else:

      outs, errs = proc.communicate()
      outs = '' if outs == None else outs.decode('utf-8')
      errs = '' if errs == None else errs.decode('utf-8')

    rc = proc.returncode

    return (rc, (outs, errs))


class TaskQueue:
  def __init__(self, python_path):
    self.work_q = Queue(maxsize=0)
    self.workers = []
    self.task_dict = {}
    self.n_threads = 0
    self.python_exec = python_path
    self.module_dir_path = os.path.dirname(os.path.realpath(__file__))
    module_file_path = os.path.join(self.module_dir_path, 'task_wrapper.py')
    self.task_wrapper = module_file_path
    self.notify = False

  def start(self,n_threads):
    if n_threads > self.n_threads:
      for i in range(n_threads - self.n_threads):
        worker = threading.Thread(target=self.run_q_item, name=str(i))
        worker.daemon = True
        self.workers.append(worker)
        worker.start()
    elif n_threads < self.n_threads:
      for i in range(self.n_threads - n_threads):
        self.work_q.put(None) # This is a signal for the thread to exit
    self.n_threads = n_threads

  def run_q_item(self):
    while True:
      task = self.work_q.get()
      if task == None:
        self.work_q.task_done()
        break

      process = task['process']
      pid = process.pid
      cmd = task['cmd']
      args = task['args']
      if self.notify:
        sys.stdout.write('Starting PID {0} {1}\n'.format(pid, cmd))
      out_q = OutputQueue()
#      sys.stdout.write('sending:  {0}\n'.format(cmd).encode().decode())
      task['status'] = 'running'
      self.task_dict[pid]['output'] = []
      rc, res = out_q.run_proc(process, arg_in=[cmd, args], passthrough=self.notify, output_list=self.task_dict[pid]['output'])
      self.task_dict[pid]['stdout'] = res[0]
      self.task_dict[pid]['stderr'] = res[1]
#      self.task_dict[pid]['text'].write(res[0])
#      self.task_dict[pid]['text'].write(res[1])
      if task['status'] != 'died':
        if rc == 0:
          task['status'] = 'completed'
        elif rc == 1:
          task['status'] = 'task_error'
        else:
          task['status'] = 'died'
      if self.notify:
        sys.stdout.write('Task PID {0}  status: {1}  return code: {2}\n'.format(pid, task['status'], rc))
      self.work_q.task_done()
    sys.stdout.write('Worker thread %s exiting\n' % (threading.currentThread().getName()))

  def clear_queue(self):
    with self.work_q.mutex:
      self.work_q.queue.clear()

  def add_task(self,cmd='',args='',wd=None,env=None):
    process = sp.Popen([self.python_exec, self.task_wrapper, wd], env=env, bufsize=1, shell=False, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
    pid = process.pid
    self.task_dict[pid] = {}
    self.task_dict[pid]['process'] = process
    self.task_dict[pid]['cmd'] = cmd
    self.task_dict[pid]['args'] = args
    self.task_dict[pid]['status'] = 'queued'
    self.task_dict[pid]['stdout'] = b''
    self.task_dict[pid]['stderr'] = b''
    self.task_dict[pid]['output'] = []
    self.work_q.put(self.task_dict[pid])
    return process

  def kill_task(self,pid):
    if self.task_dict.get(pid):
      task = self.task_dict[pid]
      if task['status'] == 'running':
        proc = task['process']
        proc.terminate()
        task['status'] = 'died'
      elif task['status'] == 'queued':
        with self.work_q.mutex:
          self.work_q.queue.remove(task)
        proc = task['process']
        proc.terminate()
        task['status'] = 'died'
        self.work_q.task_done()

  def shutdown(self):

    sys.stdout.write("Shutting down task queue...\n")

    # Send stop signal to worker threads
    for i in range(self.n_threads):
      sys.stdout.write('Stopping thread %s\n' % (self.workers[i].getName()))
      self.work_q.put(None)

    pids = list(self.task_dict.keys())

    # Dequeue waiting tasks
    for pid in pids:
      task = self.task_dict[pid]
      if task['status'] == 'queued':
        with self.work_q.mutex:
          self.work_q.queue.remove(task)
        proc = task['process']
        proc.terminate()
        task['status'] = 'died'
        self.work_q.task_done()

    # Terminate running tasks
    for pid in pids:
      task = self.task_dict[pid]
      if task['status'] == 'running':
        proc = task['process']
        proc.terminate()
        task['status'] = 'died'

    # Now wait for workers to finish and exit
    sys.stdout.write('Waiting for task worker threads to exit...\n')
    for worker in self.workers:
      worker.join()

    sys.stdout.write('Waiting for task queue to exit...\n')
    self.work_q.join()

    sys.stdout.write("Done shutting down task queue.\n")
    sys.stdout.flush()



if (__name__ == '__main__'):
  import psutil
  from argparse import ArgumentParser
  import time

  parser = ArgumentParser()
  parser.add_argument('--cpus', help='number of CPUs to use.  If omitted, use the number of hyperthreads available.')
  ns=parser.parse_args()

  my_q = TaskQueue('python')

  if ns.cpus:
    cpus = int(ns.cpus)
  else:
    cpus = psutil.cpu_count(logical=False)

  my_q.start(cpus)
  my_q.notify=True

  begin = time.time()

  wd = './task_queue_test_files/'
#  my_q.add_task('sleep', '7', wd)
#  my_q.add_task('sleep', '7', wd)
#  my_q.add_task('sleep', '7', wd)
#  my_q.add_task('sleep', '7', wd)

#  my_q.add_task('sleep 7', '', wd)
#  my_q.add_task('sleep 7', '', wd)
#  my_q.add_task('sleep 7', '', wd)
#  my_q.add_task('sleep 7', '', wd)

#  my_q.add_task('cp', 'foo.txt foo_1.txt', wd)
#  my_q.add_task('cp', 'foo.txt foo_2.txt', wd)
#  my_q.add_task('cp', 'foo.txt foo_3.txt', wd)
#  my_q.add_task('cp', 'foo.txt foo_4.txt', wd)

  my_q.add_task(cmd='cp foo.txt foo_1.txt', wd=wd)
  my_q.add_task(cmd='cp foo.txt foo_2.txt', wd=wd)
  my_q.add_task(cmd='cp foo.txt foo_3.txt', wd=wd)
  my_q.add_task(cmd='cp foo.txt foo_4.txt', wd=wd)
#  my_hello = os.path.join(my_q.module_dir_path,'hello_world.py')
#  my_q.add_task(cmd='python', args=my_hello, wd=wd)

#  my_q.add_task('sleep 7 ; cp foo.txt foo_1.txt', '', wd)
#  my_q.add_task('sleep 7 ; cp foo.txt foo_2.txt', '', wd)
#  my_q.add_task('sleep 7 ; cp foo.txt foo_3.txt', '', wd)
#  my_q.add_task('sleep 7 ; cp foo.txt foo_4.txt', '', wd)

#  my_q.add_task('mcell3.2.1 -iterations 5000 -seed 1 Scene.main.mdl',wd)
#  my_q.add_task('mcell3.2.1 -iterations 5000 -seed 2 Scene.main.mdl',wd)
#  my_q.add_task('mcell3.2.1 -iterations 5000 -seed 3 Scene.main.mdl',wd)
#  my_q.add_task('mcell3.2.1 -iterations 5000 -seed 4 Scene.main.mdl',wd)

  time.sleep(2.)

  pids = list(my_q.task_dict.keys())
  pids.sort()
#  a_pid = pids[2]
#  my_q.task_dict[a_pid]['process'].terminate()

  my_q.work_q.join()

#  print(my_q.task_dict[pids[0]]['stdout'])
#  print(my_q.task_dict[pids[0]]['stderr'])

#  time.sleep(0.5)

#  sys.stdout.write(my_q.task_dict[a_pid]['stdout'])
#  sys.stdout.write(my_q.task_dict[a_pid]['stderr'])

  sys.stdout.write('\n\nTook {0:0.2f} seconds.\n\n'.format(time.time() - begin))


