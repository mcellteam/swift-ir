#!/usr/bin/env python3

import os
import logging
import multiprocessing as mp
import subprocess as sp
import sys
import time
import queue
import inspect
import datetime

import psutil
from qtpy.QtCore import QObject
from qtpy.QtWidgets import QApplication
import neuroglancer as ng
import src.config as cfg
from src.helpers import print_exception

import numcodecs
numcodecs.blosc.use_threads = False

'''SWIM/MIR:
stdout <- result
stderr <- info + errors
'''
__all__ = ['TaskQueue']

logger = logging.getLogger(__name__)



# mpl = mp.log_to_stderr()
# mpl.setLevel(logging.INFO)

SENTINEL = 1
def worker(worker_id, task_q, result_q, n_tasks, n_workers):
    '''Function run by worker processes'''
    for task_id, task in iter(task_q.get, 'END_TASKS'):
        # QApplication.processEvents()

        logger.info('worker_id %d  task_id %d  n_tasks %d  n_workers %d' % (worker_id, task_id, n_tasks, n_workers))
        logger.debug('task: %s' % str(task))
        t0 = time.time()
        try:
            task_proc = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
            # task_proc = sp.Popen(task, shell=False, stdout=sys.stdout, stderr=sys.stderr, bufsize=1)
            outs, errs = task_proc.communicate() # assemble_recipe the task and capture output
            outs = '' if outs == None else outs.decode('utf-8')
            errs = '' if errs == None else errs.decode('utf-8')
            rc = task_proc.returncode
            logger.info('Worker %d:  Task %d Completed with RC %d\n' % (worker_id, task_id, rc))
        except:
            outs = ''
            errs = '(!) Worker %d : task exception: %s' % (worker_id, str(sys.exc_info()[0]))
            print(errs)
            rc = 1

        dt = time.time() - t0
        result_q.put((task_id, outs, errs, rc, dt)) # put method uses block=True by default
        task_q.task_done() # Pop finished task
    result_q.close()
    # result_q.join_thread()
    task_q.task_done()# Pop the Sentinel
    logger.debug('<<<< Worker %d Finished' % (worker_id))


def watchdog(wd_queue):
    """
    This check the queue for updates and send a signal to it
    when the child process isn't sending anything for too long
    """
    while True:
        try:
            msg = wd_queue.get(timeout=10.0)
        except queue.Empty as e:
            logger.critical('Watchdog Alert! Killing Worker!')
            wd_queue.put("KILL WORKER")


class TaskQueue(QObject):


    def __init__(self, n_tasks, parent=None, start_method='forkserver', pbar_text=None):
        QObject.__init__(self)
        self.parent = parent
        self.start_method = start_method
        self.ctx = mp.get_context(self.start_method)
        # self.task_dict = {}
        self.workers = []
        self.close_worker = False
        self.n_tasks = n_tasks
        self.pbar_text = pbar_text if pbar_text != None else ''
        if sys.version_info >= (3, 7):
            self.close_worker = True

        self.taskNameList = None
        self.taskPrefix = None

        self.MPQLogger = logging.getLogger('MPQLogger')
        if (self.MPQLogger.hasHandlers()):
            logger.info('Clearing MPQLogger file handlers...')
            self.MPQLogger.handlers.clear()
        self.MPQLogger.propagate = False # dont print to console
        fh = logging.FileHandler(os.path.join(cfg.data.dest(), 'logs', 'multiprocessing.log'))
        fh.setLevel(logging.DEBUG)
        self.MPQLogger.addHandler(fh)



    # def start(self, n_workers, retries=10) -> None:
    def start(self, n_workers, retries=0) -> None:

        if cfg.CancelProcesses == True:
            cfg.main_window.warn('Canceling Tasks: %s' % self.pbar_text)
            logger.warning('Canceling Tasks: %s' % self.pbar_text)
            return

        if cfg.DEBUG_MP:
            logger.info('Multiprocessing Module Debugging is ENABLED')
            mpl = mp.log_to_stderr()
            mpl.setLevel(logging.DEBUG)
        # else:
        #     mpl.setLevel(logging.INFO)

        self.work_queue = self.ctx.JoinableQueue()
        self.result_queue = self.ctx.Queue()
        self.task_dict = {}
        self.task_id = 0
        self.n_workers = min(self.n_tasks, n_workers)
        self.retries = retries

        cfg.main_window.shutdownNeuroglancer()

        if not cfg.ignore_pbar:
            cfg.main_window.showZeroedPbar() #0208+
            cfg.nCompleted += 1
            try:
                self.parent.setPbarMax(self.n_tasks)
                if self.pbar_text:
                    self.parent.setPbarText(text=self.pbar_text)
                    # self.parent.statusBar.showMessage(self.pbar_text)
                self.parent.pbar_widget.show()
                self.parent.update()
            except:
                logger.error('An exception was raised while setting up progress bar')

        logger.info('Starting Task Queue: %s...' % self.pbar_text)
        cfg.main_window.tell('Processing %d Task(s): %s' % (self.n_tasks, self.pbar_text))
        logger.critical('Processing %d Task(s): %s' % (self.n_tasks, self.pbar_text))

        for i in range(self.n_workers):
            # if i != 0: sys.stderr.write('\n')
            sys.stderr.write('Starting Worker %d >>>>' % i)
            logger.info('Starting Worker %d...' % i)
            try:
                if cfg.DAEMON_THREADS:
                    p = self.ctx.Process(target=worker, daemon=True, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, ))
                else:
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
            # time.sleep(.1)
            try:
                if cfg.DAEMON_THREADS:
                    p = self.ctx.Process(target=worker, daemon=True,
                                         args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers,))
                else:
                    p = self.ctx.Process(target=worker,
                                         args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers,))
                # p = QProcess('', [i, self.m.work_queue, self.m.result_queue, self.n_tasks, self.n_workers, self.m.pbar_q])
                self.workers.append(p)
                self.workers[i].start()
            except:
                logger.warning('Restart Worker # %d Triggered An Exception' % i)

    def end_tasks(self) -> None:
        '''Tell child processes to stop'''
        # logger.info('Ending Tasks...')
        # Add one sentinel per worker
        for i in range(self.n_workers):
            self.work_queue.put('END_TASKS')

    def stop(self) -> None:
        logger.info('Closing the Queue...')
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
        logger.warning("Requeing Task (ID: %d)..." % task_id)
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


    def get_status_of_tasks(self) -> tuple:
        n_success, n_queued, n_failed = 0, 0, 0
        for k in self.task_dict.keys():
            if self.task_dict[k]['statusBar'] == 'completed':
                n_success += 1
            elif self.task_dict[k]['statusBar'] == 'queued':
                n_queued += 1
            elif self.task_dict[k]['statusBar'] == 'task_error':
                n_failed += 1
        return n_success, n_queued, n_failed


    def collect_results(self):
        t0 = time.time()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H:%M:%S")
        try:
            self.MPQLogger.critical(f'\n\nGathering Results...\n'
                                    f'Time              : {timestamp}\n'
                                    f'len(task dict)    : {len(self.task_dict)}\n'
                                    f'Pbar Text         : {self.pbar_text}\n'
                                    f'Task Prefix       : {self.taskPrefix}\n'
                                    f'# Workers         : {self.n_workers}\n'
                                    f'Example Task      : {str(self.task_dict[0])}')
        except:
            print_exception()


        '''Run All Tasks and Collect Results'''
        logger.info(f'Running Multiprocessing Tasks ({self.retries} retries allowed)...')
        n_pending = len(self.task_dict) # <-- # images in the stack
        n_tasks = len(self.task_dict)
        realtime = n_pending
        retries_tot = 0

        logger.info('Collecting Results...')
        try:
            while (retries_tot < self.retries + 1) and n_pending:


                self.end_tasks() # Add end sentinels (one/worker)

                logger.info('# Tasks Pending   : %d' % n_pending)
                retry_list = []

                # Loop over pending tasks...
                # Update progress bar and result queue as tasks finish (mp.Queue.get() is blocking).
                for img_index,j in enumerate(range(n_pending)):
                    # task_str = self.task_dict[task_id]['cmd'] + self.task_dict[task_id]['args']
                    # logger.info(task_str)
                    if cfg.event.is_set():
                        logger.critical('Terminating Running Processes...')
                        cfg.main_window.tell('Terminating Running Processes...')
                        cfg.CancelProcesses = True
                        for w in self.workers:
                            logger.info('Terminating Process %s...' % w.name)
                            w.terminate()
                        cfg.main_window.hud.done()
                        cfg.main_window.warn('Canceling Future Tasks...')
                        self.parent.update()
                        cfg.main_window.cancelMultiprocessing.emit()
                        # QApplication.processEvents()
                        sys.exit(1)

                    if not cfg.ignore_pbar:
                        try:

                            self.parent.updatePbar(n_tasks - realtime)
                            if self.taskPrefix and self.taskNameList:
                                try:
                                    name = self.taskNameList[img_index]
                                    # self.parent.statusBar.showMessage(self.taskPrefix + name + '...', 500)
                                    self.parent.statusBar.showMessage(self.taskPrefix + name)
                                except:
                                    # print_exception()
                                    logger.warning('Improperly sized taskNameList! [size=%d] '
                                                   '[prefix=%s] '
                                                   '[n_tasks=%d]' %(len(self.taskNameList), self.taskPrefix, n_tasks))
                                QApplication.processEvents()
                        except:
                            # print_exception()
                            logger.warning(f'An exception was raised while updating progress bar [{self.taskPrefix}]')
                            print_exception()

                    # .get method is BLOCKING by default for mp.Queue
                    task_id, outs, errs, rc, dt = self.result_queue.get()

                    # logger.warning('%d%s' % (task_id,errs))  # *** lots of output for alignment
                    self.task_dict[task_id]['stdout'] = outs
                    self.task_dict[task_id]['stderr'] = errs
                    self.task_dict[task_id]['rc'] = rc
                    if rc == 0:
                        self.task_dict[task_id]['statusBar'] = 'completed'
                    else:
                        self.task_dict[task_id]['statusBar'] = 'task_error'
                        retry_list.append(task_id)
                        logger.info(f'\n_________TaskQueue.collect_results()_________\n'
                                    f'task_id : {task_id}\n'
                                    f'outs    : {outs}\n'
                                    f'errs    : {errs}'
                                    f'rc : {rc}, dt : {dt:.2f}'
                                    f'\n_____________________________________________')  # *** lots of output for alignment
                    self.task_dict[task_id]['dt'] = dt
                    realtime -= 1

                self.work_queue.join()
                self.stop() # This is called redundantly in pre-TaskQueue scripts to ensure stoppage

                '''Restart Queue and Requeue failed tasks'''
                n_pending = len(retry_list)
                if (retries_tot < self.retries) and n_pending:
                    logger.info('Requeuing Failed Tasks...')
                    logger.info('  # Failed Tasks: %d' % n_pending)
                    logger.info('  Task IDs: %s' % str(retry_list))
                    self.restart()
                    for task_id in retry_list:
                        logger.warning('Requeuing Failed Task ID: %d   Retries: %d' % (task_id, retries_tot + 1))
                        logger.warning('                    Task: %s' % (str(self.task_dict[task_id])))
                        # [logger.info(key,':',value) for key, value in self.task_dict[task_id].items()]
                        self.requeue_task(task_id)
                retries_tot += 1

            self.MPQLogger.critical('    Finished Collecting Results for %d Tasks' % (len(self.task_dict)))
            if n_pending == 0:
                logger.info('Tasks Successful  : %d' % (n_tasks - n_pending))
                logger.info('Tasks Failed      : %d' % n_pending)
                logger.info('══════ Complete ══════')

                self.MPQLogger.critical(f'Tasks Successful  : {n_tasks - n_pending}\n'
                                        f'Tasks Failed      : {n_pending}\n'
                                        f'══════ Complete [{self.pbar_text}] ══════')

                cfg.main_window.tell('Tasks Successful  : %d' % (n_tasks - n_pending))
                cfg.main_window.tell('Tasks Failed      : %d' % n_pending)
                cfg.main_window.tell('══════ Complete ══════')
            else:
                cfg.main_window.warn('Something Went Wrong')
                cfg.main_window.warn('Tasks Successful  : %d' % (n_tasks - n_pending))
                cfg.main_window.warn('Failed Tasks      : %d' % n_pending)
                cfg.main_window.warn('══════ Complete ══════')

                logger.warning('Something Went Wrong')
                logger.warning('Tasks Successful  : %d' % (n_tasks - n_pending))
                logger.warning('Failed Tasks      : %d' % n_pending)
                logger.warning('══════ Complete ══════')
        except:
            print_exception()
        finally:
            # logger.info('Checking Status of Tasks...')
            # n_success, n_queued, n_failed = 0, 0, 0
            # for task_item in self.task_dict:
            #     if task_item['statusBar'] == 'completed':
            #         logger.debug('\nCompleted:')
            #         logger.debug('   CMD:    %s' % (str(task_item['cmd'])))
            #         logger.debug('   ARGS:   %s' % (str(task_item['args'])))
            #         logger.debug('   STDERR: %s\n' % (str(task_item['stderr'])))
            #         n_success += 1
            #     elif task_item['statusBar'] == 'queued':
            #         logger.warning('\nQueued:')
            #         logger.warning('   CMD:    %s' % (str(task_item['cmd'])))
            #         logger.warning('   ARGS:   %s' % (str(task_item['args'])))
            #         logger.warning('   STDERR: %s\n' % (str(task_item['stderr'])))
            #         n_queued += 1
            #     elif task_item['statusBar'] == 'task_error':
            #         logger.error('\nTask Error:')
            #         logger.error('   CMD:    %s' % (str(task_item['cmd'])))
            #         logger.error('   ARGS:   %s' % (str(task_item['args'])))
            #         logger.error('   STDERR: %s\n' % (str(task_item['stderr'])))
            #         n_failed += 1

            # logger.critical('# TASKS: %d... SUCCESS: %d | QUEUED: %d | FAILED: %d' % (self.n_tasks, n_success, n_queued, n_failed))
            # self.parent.pbar.hide()
            dt = time.time() - t0
            # return (dt,n_success,n_queued, n_failed)
            return (dt)

        # logger.info('Exiting Task Queue scope')



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
  /Users/joelyancey/Downloads/alignEM-joel-dev-pyside6/source/src/src/job_recipe_alignment.py
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