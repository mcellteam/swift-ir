#!/usr/bin/env python3

import sys
import multiprocessing as mp
import subprocess as sp
import psutil
import time

#
# Function run by worker processes
#
def worker(worker_id, task_q, result_q):
  t_start = time.time()
  for task_id, task in iter(task_q.get, 'END_TASKS'):
    sys.stderr.write('Worker %d:  Running Task %d\n' % (worker_id, task_id))
    t0 = time.time()
    outs = ''
    errs = ''
    rc = 1
    try: 
      task_proc = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)

      outs, errs = task_proc.communicate()

      outs = '' if outs == None else outs.decode('utf-8')
      errs = '' if errs == None else errs.decode('utf-8')
      rc = task_proc.returncode
      sys.stderr.write('Worker %d:  Task %d Completed with RC %d\n' % (worker_id, task_id, rc))
    except:
      outs = ''
      errs = 'TaskQueue worker %d : task exception: %s' % (worker_id, str(sys.exc_info()[0]))
      print(errs)
      rc = 1

    dt = time.time() - t0
    result_q.put((task_id, outs, errs, rc, dt))
    task_q.task_done()

  result_q.close()
#  result_q.join_thread()
  sys.stderr.write('Worker %d:  Stopping\n' % (worker_id))
  task_q.task_done()

#  t_stop = time.time()
#  dt = t_stop - t_start
#  result_q.put((worker_id, dt))



class TaskQueue:

  def __init__(self, start_method='forkserver'):
    self.start_method = start_method
    self.ctx = mp.get_context(self.start_method)
    self.workers = []
    self.close_worker = False
    if sys.version_info >= (3, 7):
      self.close_worker = True


  def start(self, n_workers, retries=10):
    self.work_queue = self.ctx.JoinableQueue()
    self.result_queue = self.ctx.Queue()
    self.task_dict = {}
    self.task_id = 0
    self.retries = retries

    self.n_workers = n_workers
    for i in range(self.n_workers):
      p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue))
      self.workers.append(p)
      self.workers[i].start()


  def restart(self):
    sys.stderr.write('\nRestarting Task Queue...\n')
    self.work_queue = self.ctx.JoinableQueue()
    self.result_queue = self.ctx.Queue()
    self.workers=[]

    for i in range(self.n_workers):
      sys.stderr.write('    Restarting Worker %d\n' % (i))
      p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue))
      self.workers.append(p)
      self.workers[i].start()
    sys.stderr.write('    Done Restarting Task Queue\n')


  def end_tasks(self):
    # Tell child processes to stop
    for i in range(self.n_workers):
        self.work_queue.put('END_TASKS')

#    for i in range(self.n_workers):
#        worker_id, dt = self.result_queue.get()
#        print('TaskQueue worker: %d  total time: %.2f' % (worker_id, dt))


  # Stop all workers
  def stop(self):
    self.work_queue.close()
    time.sleep(0.1)  # Needed to Avoid Race Condition
#    for i in range(len(self.workers)):
#      if self.close_worker:
#        self.workers[i].close()
#      else:
#        self.workers[i].terminate()


  def add_task(self, task):
    self.task_dict[self.task_id] = {}
    self.task_dict[self.task_id]['cmd'] = task[0]
    self.task_dict[self.task_id]['args'] = task[1:]
    self.task_dict[self.task_id]['stdout'] = None
    self.task_dict[self.task_id]['stderr'] = None
    self.task_dict[self.task_id]['rc'] = None
    self.task_dict[self.task_id]['status'] = 'queued'
    self.task_dict[self.task_id]['retries'] = 0
    self.work_queue.put((self.task_id, task))
    self.task_id += 1


  def requeue_task(self, task_id):
    task = []
    task.append(self.task_dict[task_id]['cmd'])
    task.extend(self.task_dict[task_id]['args'])
    self.task_dict[task_id]['stdout'] = None
    self.task_dict[task_id]['stderr'] = None
    self.task_dict[task_id]['rc'] = None
    self.task_dict[task_id]['status'] = 'queued'
    self.task_dict[task_id]['retries'] += 1
    self.work_queue.put((task_id, task))


  def clear_tasks(self):
    self.task_dict = {}
    self.task_id = 0

 
  def collect_results(self):

    n_pending = len(self.task_dict)
    retries_tot = 0
    while (retries_tot < self.retries+1) and n_pending:

      self.end_tasks()
      self.work_queue.join()
      self.stop()

#     Get results from tasks
      retry_list = []
      for j in range(n_pending):
        task_id, outs, errs, rc, dt = self.result_queue.get()
#        sys.stderr.write('Collected results from Task_ID %d\n' % (task_id))
        self.task_dict[task_id]['stdout'] = outs
        self.task_dict[task_id]['stderr'] = errs
        self.task_dict[task_id]['rc'] = rc
        if rc == 0:
          self.task_dict[task_id]['status'] = 'completed'
        else:
          self.task_dict[task_id]['status'] = 'task_error'
          retry_list.append(task_id)
        self.task_dict[task_id]['dt'] = dt

#     Restart Queue and Requeue failed tasks
      n_pending = len(retry_list)
      if (retries_tot < self.retries) and n_pending:
        sys.stderr.write('\nNeed to Requeue %d Failed Tasks...\n' % (n_pending))
        sys.stderr.write('    Task_IDs: %s\n' % (str(retry_list)))
        self.restart()
        for task_id in retry_list:
          sys.stderr.write('Requeuing Failed Task_ID: %d   Retries: %d\n' % (task_id, retries_tot+1))
          self.requeue_task(task_id)
      retries_tot += 1

    sys.stderr.write('\nFinished Collecting Results for %d Tasks\n' % (len(self.task_dict)))
    sys.stderr.write('    Failed Tasks: %d\n' % (n_pending))
    sys.stderr.write('    Retries: %d\n\n' % (retries_tot-1))


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


    for i in range(2*cpus):
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

