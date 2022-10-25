#!/usr/bin/env python3

import io
import sys
import time
import psutil
import inspect
import logging
import subprocess as sp
import multiprocessing as mp
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication
import src.config as cfg
from src.helpers import print_exception


'''SWIM/MIR:
stdout <- result
stderr <- info + errors
'''
__all__ = ['TaskQueue']

logger = logging.getLogger(__name__)
mpl = mp.log_to_stderr()
# mpl.setLevel(logging.INFO)

SENTINEL = 1
def worker(worker_id, task_q, result_q, n_tasks, n_workers):
    '''Function run by worker processes'''
    time.sleep(.1)

    for task_id, task in iter(task_q.get, 'END_TASKS'):
        QApplication.processEvents()

        logger.debug('worker_id %d  task_id %d  n_tasks %d  n_workers %d' % (worker_id, task_id, n_tasks, n_workers))
        logger.debug('task: %s' % str(task))
        t0 = time.time()
        try:
            task_proc = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
            # task_proc = sp.Popen(task, shell=False, stdout=sys.stdout, stderr=sys.stderr, bufsize=1)
            outs, errs = task_proc.communicate()
            outs = '' if outs == None else outs.decode('utf-8')
            errs = '' if errs == None else errs.decode('utf-8')
            rc = task_proc.returncode
            logger.debug('Worker %d:  Task %d Completed with RC %d\n' % (worker_id, task_id, rc))
        except:
            outs = ''
            errs = 'Worker %d : task exception: %s' % (worker_id, str(sys.exc_info()[0]))
            print(errs)
            rc = 1

        dt = time.time() - t0
        result_q.put((task_id, outs, errs, rc, dt)) # put method uses block=True by default
        task_q.task_done()
    result_q.close()
    # result_q.join_thread()
    task_q.task_done()
    logger.debug('<<<< Worker %d Finished' % (worker_id))


class TaskQueue(QObject):
    # def __init__(self, n_tasks, start_method='forkserver', progress_callback=None):
    def __init__(self, n_tasks, parent=None, start_method='forkserver',logging_handler=None, pbar_text=None):
        self.parent = parent
        self.start_method = start_method
        self.ctx = mp.get_context(self.start_method)
        # self.task_dict = {}
        self.workers = []
        self.close_worker = False
        self.n_tasks = n_tasks
        self.pbar_text = pbar_text
        if sys.version_info >= (3, 7):
            self.close_worker = True
        self.logging_handler = logging_handler
        # self.work_queue = self.ctx.JoinableQueue()
        # self.result_queue = self.ctx.Queue()

        logger.info('TaskQueue Initialization')
        logger.info('self.start_method = %s' % self.start_method)
        logger.info('self.close_worker = %s' % str(self.close_worker))
        logger.info('self.n_tasks = %d' % self.n_tasks)
        logger.info('sys.version_info = %s' % str(sys.version_info))

    # def start(self, n_workers, retries=10) -> None:
    def start(self, n_workers, retries=3) -> None:
        logger.debug('>>>> TaskQueue.start >>>>')
        self.work_queue = self.ctx.JoinableQueue()
        self.result_queue = self.ctx.Queue()
        self.task_dict = {}
        self.task_id = 0
        self.n_workers = n_workers
        self.retries = retries
        self.task_dict = {}
        if cfg.DEBUG_MP:
            mpl.setLevel(logging.DEBUG)
        else:
            mpl.setLevel(logging.INFO)

        cfg.main_window.hud.post('%d Workers Are Processing %d tasks' % (self.n_workers, self.n_tasks))

        for i in range(self.n_workers):
            if i != 0: sys.stderr.write('\n')
            sys.stderr.write('Starting Worker %d >>>>' % i)
            try:
                # p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, ))
                # p = self.ctx.Process(target=worker, daemon=True, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, ))
                p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, ))
                # p = QProcess('', [i, self.m.work_queue, self.m.result_queue, self.n_tasks, self.n_workers, self.m.pbar_q])
                self.workers.append(p)
                self.workers[i].start()
            except:
                logger.warning('Original Worker # %d Triggered An Exception' % i)
        logger.debug('<<<< Exiting TaskQueue.start <<<<')

    def restart(self) -> None:
        logger.warning('Restarting the Task Queue...')
        self.work_queue = self.ctx.JoinableQueue()
        self.result_queue = self.ctx.Queue()
        self.workers = []

        for i in range(self.n_workers):
            sys.stderr.write('Restarting Worker %d >>>>' % i)
            try:
                # p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, ))
                # p = self.ctx.Process(target=worker, daemon=True, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, ))
                p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, ))
                # p = QProcess('', [i, self.m.work_queue, self.m.result_queue, self.n_tasks, self.n_workers, self.m.pbar_q])
                self.workers.append(p)
                self.workers[i].start()
            except:
                logger.warning('Restart Worker # %d Triggered An Exception' % i)

    def end_tasks(self) -> None:
        '''Tell child processes to stop'''
        logger.info("'Calling 'end_tasks' on Task Queue")
        for i in range(self.n_workers):
            self.work_queue.put('END_TASKS')

    def stop(self) -> None:
        logger.info("Calling 'stop' on Task Queue")
        self.work_queue.close()
        time.sleep(0.1)  # Needed to Avoid Race Condition
    #    for i in range(len(self.workers)):
    #      if self.close_worker: self.workers[i].close()
    #      else: self.workers[i].terminate()

    def add_task(self, task) -> None:
        self.task_dict[self.task_id] = {}
        self.task_dict[self.task_id]['cmd'] = task[0]
        self.task_dict[self.task_id]['args'] = task[1:]
        self.task_dict[self.task_id]['stdout'] = None
        self.task_dict[self.task_id]['stderr'] = None
        self.task_dict[self.task_id]['rc'] = None
        self.task_dict[self.task_id]['statusBar'] = 'queued'
        self.task_dict[self.task_id]['retries'] = 0
        self.work_queue.put((self.task_id, task)) # <-- one-by-one calls to 'TaskQueue.add_task' adds each task to the queue
        self.task_id += 1

    def requeue_task(self, task_id) -> None:
        logger.debug(">>>> TaskQueue.requeue  >>>>")
        task = []
        task.append(self.task_dict[task_id]['cmd'])
        task.extend(self.task_dict[task_id]['args'])
        self.task_dict[task_id]['stdout'] = None
        self.task_dict[task_id]['stderr'] = None
        self.task_dict[task_id]['rc'] = None
        self.task_dict[task_id]['statusBar'] = 'queued'
        self.task_dict[task_id]['retries'] += 1
        self.work_queue.put((task_id, task))
        logger.debug("<<<<  TaskQueue.requeue <<<<")

    def clear_tasks(self) -> None:
        self.task_dict = {}
        self.task_id = 0


    def collect_results(self) -> None:
        '''Run All Tasks and Collect Results'''
        print('\n')
        logger.critical('>>>> Task Queue (collect_results) >>>>')
        logger.info('mp.get_start_method() = %s' % str(mp.get_start_method()))
        logger.info('mp.get_context() = %s' % str(mp.get_context()))
        # logger.info('mp.log_to_stderr() = %s' % str(mp.log_to_stderr())) #?
        logger.info('mp.cpu_count() = %s' % str(mp.cpu_count()))
        logger.info(mp.get_context())
        # cfg.main_window.hud.post('Collecting Results...')
        n_pending = len(self.task_dict) # <-- # images in the stack
        realtime = n_pending
        retries_tot = 0
        logger.info('# Retries Allowed: %s' % self.retries)
        try:
            self.parent.pbar_max(self.n_tasks)
            if self.pbar_text != None:
                self.parent.setPbarText(text=self.pbar_text)
            self.parent.pbar.show()
        except:
            print_exception()
        while (retries_tot < self.retries + 1) and n_pending:
            logger.info('# Tasks Pending: %d' % n_pending)
            # self.end_tasks()
            # self.work_queue.join()
            # self.stop() # This is called redundantly in pre-TaskQueue scripts to ensure stoppage
            retry_list = []
            for j in range(n_pending):
                # task_str = self.task_dict[task_id]['cmd'] + self.task_dict[task_id]['args']
                # logger.info(task_str)
                try:     self.parent.pbar_update(self.n_tasks - realtime)
                except:  print_exception()
                task_id, outs, errs, rc, dt = self.result_queue.get()
                # logger.warning('Task ID (outs): %d\n%s' % (task_id,outs))
                # logger.warning('%d%s' % (task_id,errs))  # *** lots of output for alignment
                self.task_dict[task_id]['stdout'] = outs
                self.task_dict[task_id]['stderr'] = errs
                self.task_dict[task_id]['rc'] = rc
                self.task_dict[task_id]['statusBar'] = 'completed' if rc == 0 else 'task_error'
                if rc != 0:  retry_list.append(task_id)
                self.task_dict[task_id]['dt'] = dt

                realtime -= 1

            '''Restart Queue and Requeue failed tasks'''
            n_pending = len(retry_list)
            if (retries_tot < self.retries) and n_pending:
                logger.info('Requeuing Failed Tasks...')
                logger.info('  # Failed Tasks: %d' % n_pending)
                logger.info('  Task IDs: %s' % str(retry_list))

                self.restart()
                for task_id in retry_list:
                    logger.info('Requeuing Failed Task ID: %d   Retries: %d' % (task_id, retries_tot + 1))
                    logger.info('                    Task: %s' % (str(self.task_dict[task_id])))
                    # [logger.info(key,':',value) for key, value in self.task_dict[task_id].items()]
                    self.requeue_task(task_id)
            retries_tot += 1
        logger.debug('    Finished Collecting Results for %d Tasks\n' % (len(self.task_dict)))
        logger.debug('    Failed Tasks: %d\n' % (n_pending))
        logger.debug('    Retries: %d\n\n' % (retries_tot - 1))
        if n_pending == 0:
            logger.info('Failed Tasks   : %d' % n_pending)
            logger.info('Retries        : %d' % (retries_tot - 1))
            logger.info('Complete')
        else:
            logger.error('Something Went Wrong')
            logger.error('Failed Tasks  : %d' % n_pending)
            logger.error('Retries       : %d' % (retries_tot - 1))
            logger.error('Complete')

        # self.end_tasks()
        # self.work_queue.join()
        # self.stop() # This is called redundantly in pre-TaskQueue scripts to ensure stoppage
        self.parent.pbar.hide()

        logger.critical('<<<< Task Queue (collect_results) <<<<')



if __name__ == '__main__':
    print("Running " + __file__ + ".__main__()")

    # mp.freeze_support()
    tq = TaskQueue()
    cpus = psutil.cpu_count(logical=False)
    tq.start(cpus)

    tasks = []

    for i in range(2 * cpus):
        tasks.append(['./demo_datamodel_read.py'])

    print('\n>>>> Submitting Tasks: >>>>\n')
    for task in tasks:
        tq.add_task(task)

    print('\n>>>> Collecting Results: >>>>\n')
    tq.collect_results()

    print('\n>>>> Task Results: >>>>\n')
    for task_id in tq.task_dict:
        print('[task %s]: %s %s %s %s %s' %
              (str(task_id),
               str(tq.task_dict[task_id]['cmd']),
               str(tq.task_dict[task_id]['args']),
               str(tq.task_dict[task_id]['rc']),
               str(tq.task_dict[task_id]['statusBar']),
               str(tq.task_dict[task_id]['dt'])))

        print('\n%s\n' % (tq.task_dict[task_id]['stdout']))


'''

task= ['/Users/joelyancey/.local/share/virtualenvs/alignEM-AuCIf4YN/bin/python3', 
       '/Users/joelyancey/glanceem_swift/alignEM/source/src/src/job_python_apply_affine.py', 
       '-gray', 
       '-afm', 
       '1.040024184796598', 
       '-0.06164416771039566', 
       '6.129211454835417', 
       '-0.03361544745367374', 
       '1.1675729687524627', 
       '-49.218610253016884', 
       '/Users/joelyancey/glanceem_swift/test_projects/test1/scale_4/img_src/R34CA1-BS12.105.tif', 
       '/Users/joelyancey/glanceem_swift/test_projects/test1/scale_4/img_aligned/R34CA1-BS12.105.tif']
    
    
generate_scales task (example)
task = ['/Users/joelyancey/glanceem_swift/alignEM/source/src/src//lib/bin_darwin/iscale2', 
        '+4', 
        'of=/Users/joelyancey/glanceem_swift/test_projects/test16/scale_4/img_src/R34CA1-BS12.117.tif', 
        '/Users/joelyancey/glanceem_swift/test_projects/test16/scale_1/img_src/R34CA1-BS12.117.tif']


Good example of a single_alignment_job run:
project_runner.do_alignment | Starting mp_queue with args:
  /Users/joelyancey/.local/share/virtualenvs/alignEM-AuCIf4YN/bin/python3
  /Users/joelyancey/Downloads/alignEM-joel-dev-pyside6/source/src/src/job_single_alignment.py
  /Users/joelyancey/glanceem_swift/test_projects/test_last_push/project_runner_job_file.json
  init_affine
  4
  c
  9
  1
  0


OMP_NUM_THREADS=1 <- turns off OpenMP multi-threading, so each Python process remains single-threaded.

multiprocess is a fork of multiprocessing. multiprocess extends multiprocessing to provide enhanced serialization, 
using dill. multiprocess leverages multiprocessing to support the spawning of processes using the API of the python 
standard library’s threading module. multiprocessing has been distributed as part of the standard library since 
python 2.6.

Local
SWIM argument string: ww_3328x3328 -i 2 -w -0.68 -x 0 -y 0 -k  /Users/joelyancey/glanceEM_SWiFT/test_projects/2imgs_test_2/scale_1/k_img  /Users/joelyancey/glanceEM_SWiFT/test_projects/2imgs_test_2/scale_1/img_src/R34CA1-BS12.101.tif 2048 2048 /Users/joelyancey/glanceEM_SWiFT/test_projects/2imgs_test_2/scale_1/img_src/R34CA1-BS12.102.tif 2048.000000 2048.000000  1.000000 0.000000 -0.000000 1.000000

LoneStar6
SWIM argument string: ww_208 -i 2 -w -0.68 -x 128 -y 384 -k keep.JPG -d /Users/joelyancey/glanceEM_SWiFT/test_projects/quik3/scale_4 /Users/joelyancey/glanceEM_SWiFT/test_projects/quik3/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/quik3/scale_4/img_src/R34CA1-BS12.102.tif 509.351200 513.196671  1.007430 0.003800 -0.000115 1.050630

'''