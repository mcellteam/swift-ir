#!/usr/bin/env python3

import sys
import multiprocessing as mp
import subprocess as sp
import psutil
import time


class TaskQueue:

  def __init__(self, start_method='forkserver'):
    self.ctx = mp.get_context(start_method)


  def start(self, n_workers):
    self.work_queue = self.ctx.JoinableQueue()
    self.result_queue = self.ctx.Queue()
    self.task_dict = {}
    self.task_id = 0

    self.n_workers = n_workers
    for i in range(self.n_workers):
      self.ctx.Process(target=self.worker, args=(i, self.work_queue, self.result_queue)).start()


  def stop(self):
    # Tell child processes to stop
    for i in range(self.n_workers):
        self.work_queue.put('STOP')
#    for i in range(self.n_workers):
#        worker_id, dt = self.result_queue.get()
#        print('TaskQueue worker: %d  total time: %.2f' % (worker_id, dt))

  #
  # Function run by worker processes
  #
  def worker(self, worker_id, task_q, result_q):
    t_start = time.time()
    for task_id, task in iter(task_q.get, 'STOP'):

      t0 = time.time()
      try: 
#        process = sp.Popen(task, cwd=work['wd'], env=work['env'], bufsize=1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)

        task_proc = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)

        outs, errs = task_proc.communicate()

        outs = '' if outs == None else outs.decode('utf-8')
        errs = '' if errs == None else errs.decode('utf-8')
        rc = task_proc.returncode
      except:
        outs = ''
        errs = 'TaskQueue worker %d : task exception: %s' % (worker_id, str(sys.exc_info()[0]))
        print(errs)
        rc = 1

      task_q.task_done()
      dt = time.time() - t0

      result_q.put((task_id, outs, errs, rc, dt))

    task_q.task_done()

#    t_stop = time.time()
#    dt = t_stop - t_start
#    result_q.put((worker_id, dt))


  def add_task(self, task):
    self.task_dict[self.task_id] = {}
    self.task_dict[self.task_id]['cmd'] = task[0]
    self.task_dict[self.task_id]['args'] = task[1:]
    self.task_dict[self.task_id]['stdout'] = None
    self.task_dict[self.task_id]['stderr'] = None
    self.task_dict[self.task_id]['rc'] = None
    self.task_dict[self.task_id]['status'] = 'queueud'
    self.work_queue.put((self.task_id, task))
    self.task_id += 1


  def clear_tasks(self):
    self.task_dict = {}
    self.task_id = 0

 
  def collect_results(self, stop=True):

    if stop:
      self.stop()

    self.work_queue.join()

    for i in range(len(self.task_dict)):
        task_id, outs, errs, rc, dt = self.result_queue.get()
        self.task_dict[task_id]['stdout'] = outs
        self.task_dict[task_id]['stderr'] = errs
        self.task_dict[task_id]['rc'] = rc
        if rc == 0:
          self.task_dict[task_id]['status'] = 'completed'
        else:
          self.task_dict[task_id]['status'] = 'task_error'
        self.task_dict[task_id]['dt'] = dt


if __name__ == '__main__':
#    mp.freeze_support()

    tq = TaskQueue()
    cpus = psutil.cpu_count(logical=False)
#    cpus = 8
    tq.start(cpus)

    tasks = []
#    tasks.append(['ls','./'])
#    tasks.append(['ls','../'])
#    tasks.append(['echo','\n>>>>>> hello world!!! <<<<<<\n'])

#    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])
#    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])
#    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])
#    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])


    for i in range(cpus):
      tasks.append(['./demo_datamodel_read.py'])

    print('\n>>>>>> Submitting Tasks: <<<<<<\n')
    for task in tasks:
      tq.add_task(task)

    print('\n>>>>>> Collecting Results: <<<<<<\n')
    tq.collect_results()

    print('\n>>>>>> Task Results: <<<<<<\n')
    for task_id in tq.task_dict:
        print( '[task %s]: %s %s %s %s %s' % 
               (str(task_id),
               str(tq.task_dict[task_id]['cmd']),
               str(tq.task_dict[task_id]['args']),
               str(tq.task_dict[task_id]['rc']),
               str(tq.task_dict[task_id]['status']),
               str(tq.task_dict[task_id]['dt']) ))

        print('\n%s\n' % (tq.task_dict[task_id]['stdout']))


    '''
    tq.start(cpus)

    print('\n>>>>>> Submitting Tasks Again: <<<<<<\n')
    for task in tasks:
      tq.add_task(task)

    print('\n>>>>>> Collecting Results Again: <<<<<<\n')
    tq.collect_results()

    print('\n>>>>>> More Task Results: <<<<<<\n')
    for task_id in tq.task_dict:
        print( '[task %s]: %s %s %s %s %s' % 
               (str(task_id),
               str(tq.task_dict[task_id]['cmd']),
               str(tq.task_dict[task_id]['args']),
               str(tq.task_dict[task_id]['rc']),
               str(tq.task_dict[task_id]['status']),
               str(tq.task_dict[task_id]['dt']) ))

        print('\n%s\n' % (tq.task_dict[task_id]['stdout']))
    '''

