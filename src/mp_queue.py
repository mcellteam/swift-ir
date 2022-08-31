#!/usr/bin/env python3

import io
import sys
import time
import psutil
import inspect
import logging
from tqdm import tqdm
import subprocess as sp
import multiprocessing as mp
from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication
# from .LoggingTqdm import logging_tqdm
# from .TqdmToLogger import tqdm_to_logger

'''SWIM/MIR:
stdout <- result
stderr <- info + errors
'''
__all__ = ['TaskQueue']

logger = logging.getLogger(__name__)
# logger = logging.getLogger("hud")
# logger_tqdm = logging_tqdm(logging.getLogger("hud"))
mpl = mp.log_to_stderr()
mpl.setLevel(logging.CRITICAL)

class TqdmToLogger(io.StringIO):
    """
        Output stream for TQDM which will output to logger module instead of
        the StdOut.
    """
    logger = None
    level = None
    buf = ''
    def __init__(self,logger,level=None):
        super(TqdmToLogger, self).__init__()
        self.logger = logger
        self.level = level or logging.INFO
    def write(self,buf):
        self.buf = buf.strip('\r\n\t ')
    def flush(self):
        self.logger.log(self.level, self.buf)


SENTINEL = 1
def worker(worker_id, task_q, result_q, n_tasks, n_workers, pbar_q = None):
    '''Function run by worker processes'''
    time.sleep(.1)
    pbar_q.put(SENTINEL)

    for task_id, task in iter(task_q.get, 'END_TASKS'):
        QApplication.processEvents()

        logger.critical('worker_id %d    task_id %d    n_tasks %d    n_workers %d :' % (worker_id, task_id, n_tasks, n_workers))
        logger.critical('task: %s' % str(task))
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
            logger.debug('Worker %d:  Task %d Completed with RC %d\n' % (worker_id, task_id, rc))
        except:
            outs = ''
            errs = 'Worker %d : task exception: %s' % (worker_id, str(sys.exc_info()[0]))
            print(errs)
            rc = 1

        pbar_q.put(SENTINEL)
        dt = time.time() - t0
        result_q.put((task_id, outs, errs, rc, dt)) # put method uses block=True by default
        task_q.task_done()
    result_q.close()
    # result_q.join_thread()
    task_q.task_done()
    # task_q.close() #jy
    # time.sleep(1)
    logger.debug('<<<< Worker %d Finished' % (worker_id))


class TaskQueue(QObject):
    # def __init__(self, n_tasks, start_method='forkserver', progress_callback=None):
    def __init__(self, n_tasks, parent=None, start_method='forkserver',logging_handler=None):
        self.parent = parent
        self.start_method = start_method
        self.ctx = mp.get_context(self.start_method)
        self.task_dict = {}
        self.workers = []
        self.close_worker = False
        self.n_tasks = n_tasks
        if sys.version_info >= (3, 7):
            self.close_worker = True
        self.logging_handler = logging_handler
        self.work_queue = self.ctx.JoinableQueue()
        self.result_queue = self.ctx.Queue()
        self.pbar_q = self.ctx.Queue()
        self.tqdm_desc = ''

        logger.debug('TaskQueue Initialization')
        logger.debug('self.start_method = %s' % self.start_method)
        logger.debug('self.close_worker = %s' % str(self.close_worker))
        logger.debug('self.n_tasks = %d' % self.n_tasks)
        logger.debug('sys.version_info = %s' % str(sys.version_info))

    def pbar_listener(self, pbar_q, n_tasks:int):
        pass
        '''self.progress_callback has an identical location in memory'''
        # tqdm_out = TqdmToLogger(logging.getLogger("hud"), level=logging.INFO)
        # pbar = tqdm(total = n_tasks, desc=self.tqdm_desc)
        # # pbar = tqdm(total = n_tasks, desc=self.tqdm_desc, file=tqdm_out)
        # # pbar = logger_tqdm(total = n_tasks, desc=self.tqdm_desc)
        # # pbar = logging_tqdm()
        # for item in iter(pbar_q.get, None):
        #     pbar.update()
        # pbar.close()

    def start(self, n_workers, retries=1) -> None:

        '''type(task_q)= <class 'multiprocessing.queues.JoinableQueue'>
           type(result_q)= <class 'multiprocessing.queues.Queue'>'''
        logger.debug('TaskQueue.start:')
        logger.info('Size of Task Dict: %d' % len(self.task_dict))
        self.task_id = 0
        self.n_workers = n_workers

        logger.info('Number of Workers: %d' % self.n_workers)
        self.retries = retries
        self.task_dict = {}

        logger.info('Using %d workers in parallel to process a batch of %d tasks' % (self.n_workers, self.n_tasks))
        # pbar_proc = QProcess(target=self.pbar_listener, args=(self.m.pbar_q, self.n_tasks))
        try:
            # self.pbar_proc = self.ctx.Process(target=self.pbar_listener, daemon=True, args=(self.pbar_q, self.n_tasks, ))
            self.pbar_proc = self.ctx.Process(target=self.pbar_listener, args=(self.pbar_q, self.n_tasks, ))
            self.pbar_proc.start()
        except:
            logger.warning('There Was a Problem Launching the Progress Bar Process')

        for i in range(self.n_workers):
            sys.stderr.write('Starting Worker %d >>>>>>>>' % i)
            try:
                # p = self.ctx.Process(target=worker, daemon=True, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, self.pbar_q, ))
                p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, self.pbar_q, ))
                # p = QProcess('', [i, self.m.work_queue, self.m.result_queue, self.n_tasks, self.n_workers, self.m.pbar_q])
                self.workers.append(p)
                self.workers[i].start()
            except:
                logger.warning('Launching Worker # %d Triggered An Exception' % i)
        logger.debug('<<<< Exiting TaskQueue.start')

    def restart(self) -> None:
        logger.debug('TaskQueue.restart:')
        logger.info('Restarting the Task Queue...')
        self.work_queue = self.ctx.JoinableQueue()
        self.result_queue = self.ctx.Queue()
        self.pbar_q = self.ctx.Queue()
        self.workers = []
        try:
            # self.pbar_proc = self.ctx.Process(target=self.pbar_listener, daemon=True, args=(self.pbar_q, self.n_tasks,))
            self.pbar_proc = self.ctx.Process(target=self.pbar_listener, args=(self.pbar_q, self.n_tasks, ))
            self.pbar_proc.start()
        except:
            logger.warning('There Was a Problem Launching the Progress Bar Process')
        for i in range(self.n_workers):
            sys.stderr.write('Restarting Worker %d >>>>' % i)
            try:
                # p = self.ctx.Process(target=worker, daemon=True, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, self.pbar_q,))
                p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, self.pbar_q, ))
                # p = QProcess('', [i, self.m.work_queue, self.m.result_queue, self.n_tasks, self.n_workers, self.m.pbar_q])
                self.workers.append(p)
                self.workers[i].start()
            except:
                logger.warning('Restarting Worker # %d Triggered An Exception' % i)

    def end_tasks(self) -> None:
        '''Tell child processes to stop'''
        logger.debug('TaskQueue.end_tasks:')
        for i in range(self.n_workers):
            self.work_queue.put('END_TASKS')
        logger.debug('<<<< TaskQueue.end_tasks')

    def stop(self) -> None:
        logger.info("Calling 'stop' on TaskQueue")
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
        self.task_dict[self.task_id]['status'] = 'queued'
        self.task_dict[self.task_id]['retries'] = 0
        self.work_queue.put((self.task_id, task)) # <-- one-by-one calls to 'TaskQueue.add_task' adds each task to the queue
        self.task_id += 1

    def requeue_task(self, task_id) -> None:
        logger.debug("TaskQueue.requeue  >>>>>>>>")
        task = []
        task.append(self.task_dict[task_id]['cmd'])
        task.extend(self.task_dict[task_id]['args'])
        self.task_dict[task_id]['stdout'] = None
        self.task_dict[task_id]['stderr'] = None
        self.task_dict[task_id]['rc'] = None
        self.task_dict[task_id]['status'] = 'queued'
        self.task_dict[task_id]['retries'] += 1
        self.work_queue.put((task_id, task))
        logger.debug("<<<<<<<<  TaskQueue.requeue")

    def clear_tasks(self) -> None:
        self.task_dict = {}
        self.task_id = 0

    # def count_tasks(self) -> int:
    #     '''This does not work. It would be nice if it did.'''
    #     return len(self.task_dict)

    def collect_results(self) -> None:

        logger.critical('Caller: %s' % inspect.stack()[1].function)
        '''Get results from tasks'''
        logger.info("TaskQueue.collect_results  >>>>")
        # cfg.main_window.hud.post('Collecting Results...')
        n_pending = len(self.task_dict) # <-- # images in the stack
        realtime = n_pending
        retries_tot = 1
        while (retries_tot < self.retries + 1) and n_pending:
            logger.info('# Tasks Pending: %d' % n_pending)
            retry_list = []
            for j in range(n_pending):
                try:
                    task_str = self.task_dict[task_id]['cmd'] + self.task_dict[task_id]['args']
                    logger.critical(task_str)
                except:
                    pass

                logger.info('# Tasks Remaining: %d' % realtime)
                self.parent.pbar.show()
                QApplication.processEvents() # allows Qt to continue to respond so application will stay responsive.
                self.parent.pbar_update(self.n_tasks - realtime)
                task_id, outs, errs, rc, dt = self.result_queue.get()
                logger.warning('Collected results from Task_ID %d' % (task_id))
                logger.warning('Task ID (outs): %d\n%s' % (task_id,outs))
                # logger.warning('%d%s' % (task_id,errs)) # lots of output for alignment
                self.task_dict[task_id]['stdout'] = outs
                self.task_dict[task_id]['stderr'] = errs
                self.task_dict[task_id]['rc'] = rc

                if rc == 0:
                    self.task_dict[task_id]['status'] = 'completed'
                else:
                    self.task_dict[task_id]['status'] = 'task_error'
                    retry_list.append(task_id)
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

        self.parent.pbar.hide()
        self.end_tasks()
        self.work_queue.join()
        self.stop()

        logger.info('<<<<  TaskQueue.collect_results')



if __name__ == '__main__':
    print("Running " + __file__ + ".__main__()")

    # mp.freeze_support()
    tq = TaskQueue()
    cpus = psutil.cpu_count(logical=False)
    tq.start(cpus)

    tasks = []

    for i in range(2 * cpus):
        tasks.append(['./demo_datamodel_read.py'])

    print('\n>>>>>> Submitting Tasks: <<<<<<\n')
    for task in tasks:
        tq.add_task(task)

    print('\n>>>>>> Collecting Results: <<<<<<\n')
    tq.collect_results()

    print('\n>>>>>> Task Results: <<<<<<\n')
    for task_id in tq.task_dict:
        print('[task %s]: %s %s %s %s %s' %
              (str(task_id),
               str(tq.task_dict[task_id]['cmd']),
               str(tq.task_dict[task_id]['args']),
               str(tq.task_dict[task_id]['rc']),
               str(tq.task_dict[task_id]['status']),
               str(tq.task_dict[task_id]['dt'])))

        print('\n%s\n' % (tq.task_dict[task_id]['stdout']))


'''
Pickling issues:
https://stackoverflow.com/questions/32856206/pickling-issue-with-python-pathos?newreg=11b52c7f24714b76b4fa3ad8462dc658
Gracefully exiting w/ Python multiprocessing:
https://the-fonz.gitlab.io/posts/python-multiprocessing/
Mercurial solved this by just removing the __reduce__  method, hah!
https://hg.python.org/cpython/rev/c2910971eb86
The process has forked and you cannot use this CoreFoundation functionality safely. You MUST exec().
Break on __THE_PROCESS_HAS_FORKED_AND_YOU_CANNOT_USE_THIS_COREFOUNDATION_FUNCTIONALITY___YOU_MUST_EXEC__() to debug.
dill.copy(self.pbar_proc) # <-- debug dill pickling issues
^^
TypeError: Pickling an AuthenticationString object is disallowed for security reasons
RuntimeError: Queue objects should only be shared between processes through inheritance
run() method is an inbuilt method of the Thread class of the threading module in Python. This method is used to
represent a thread's activity. It calls the method expressed as the target argument in the Thread object along with
the positional and keyword arguments taken from the args and kwargs arguments, respectively.
QProcess Example:
p = QProcess()
p.start("python3", ['dummy_script.py'])
multiprocessing module only
print('mp_queue.TaskQueue.start | type(self.progress_callback) = ', type(self.progress_callback))
print('mp_queue.TaskQueue.start | str(self.progress_callback) = ', str(self.progress_callback))
print('mp_queue.TaskQueue.start | mp.parent_process() = ', mp.parent_process())
print('mp_queue.TaskQueue.start | mp.get_context() = ', mp.get_context())
print('mp_queue.TaskQueue.start | mp.get_start_method() = ', mp.get_start_method())
image_apply_affine task (example)
task= ['/Users/joelyancey/.local/share/virtualenvs/alignEM-AuCIf4YN/bin/python3', 
       '/Users/joelyancey/glanceem_swift/alignEM/source/src/src/job_apply_affine.py', 
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
'''


#------------------------------------------------------
'''
PROBLEMATIC
INFO:interface:
Task Error:
INFO:interface:   CMD:    /Users/joelyancey/.local/share/virtualenvs/alignEM-AuCIf4YN/bin/python3
INFO:interface:   ARGS:   ['/Users/joelyancey/glanceem_swift/alignEM/source/src/src/job_single_alignment.py', '/Users/joelyancey/glanceEM_SWiFT/test_projects/full_volume_josef_2/project_runner_job_file.json', 'init_affine', '4', 'c', '127', '1', '1']
INFO:interface:   STDERR: /Users/joelyancey/.local/share/virtualenvs/alignEM-AuCIf4YN/bin/python3: can't open file '/Users/joelyancey/glanceem_swift/alignEM/source/src/src/job_single_alignment.py': [Errno 2] No such file or directory
What a good single_alignment_job run looks like:
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
HOW IS ^^ THAT DIFFERENT FROM THIS:
Starting mp_queue with args:
  /Users/joelyancey/.local/share/virtualenvs/alignEM-AuCIf4YN/bin/python3
  /Users/joelyancey/glanceem_swift/alignEM/source/src/src/src/job_single_alignment.py
  /Users/joelyancey/glanceEM_SWiFT/test_projects/test94/project_runner_job_file.json
  init_affine
  4
  c
  14
  1
  0
'''






'''
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
        This probably means that you are not using fork to start your
        child processes and you have forgotten to use the proper idiom
        in the main module:
            if __name__ == '__main__':
                freeze_support()
                ...
        The "freeze_support()" line can be omitted if the program
        is not going to be frozen to produce an executable.
'''


'''
p = ctx.Process()
pickle.dumps(p._config['authkey'])
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/Users/joelyancey/.local/share/virtualenvs/alignEM-AuCIf4YN/lib/python3.9/site-packages/multiprocess/process.py", line 347, in __reduce__
    raise TypeError(
TypeError: Pickling an AuthenticationString object is disallowed for security reasons
'''



'''class AuthenticationString(bytes):
    def __reduce__(self):
        from .context import get_spawning_popen
        if get_spawning_popen() is None:
            raise TypeError(
                'Pickling an AuthenticationString object is '
                'disallowed for security reasons'
                )
        return AuthenticationString, (bytes(self),)'''


'''
consider using:
PYTHONOPTIMIZE=1 and 
OMP_NUM_THREADS
OMP_NUM_THREADS=1 <--  turns off the OpenMP multi-threading, so each of your Python processes remains single-threaded.
'''

'''
multiprocess is a fork of multiprocessing. multiprocess extends multiprocessing to provide enhanced serialization, 
using dill. multiprocess leverages multiprocessing to support the spawning of processes using the API of the python 
standard library’s threading module. multiprocessing has been distributed as part of the standard library since 
python 2.6.
'''


'''
REPLICATE THE AuthenticationString ISSUE:
from multiprocessing import Process
import pickle
p = Process()
pickle.dumps(p._config['authkey'])
'''



'''
Eyedea
SWIM argument string: ww_3328x3328 -i 2 -w -0.68 -x 0 -y 0 -k  /Users/joelyancey/glanceEM_SWiFT/test_projects/2imgs_test_2/scale_1/k_img  /Users/joelyancey/glanceEM_SWiFT/test_projects/2imgs_test_2/scale_1/img_src/R34CA1-BS12.101.tif 2048 2048 /Users/joelyancey/glanceEM_SWiFT/test_projects/2imgs_test_2/scale_1/img_src/R34CA1-BS12.102.tif 2048.000000 2048.000000  1.000000 0.000000 -0.000000 1.000000


LoneStar6

SWIM argument string: ww_208 -i 2 -w -0.68 -x 128 -y 384 -k keep.JPG -d /Users/joelyancey/glanceEM_SWiFT/test_projects/quik3/scale_4 /Users/joelyancey/glanceEM_SWiFT/test_projects/quik3/scale_4/img_src/R34CA1-BS12.101.tif 512 512 /Users/joelyancey/glanceEM_SWiFT/test_projects/quik3/scale_4/img_src/R34CA1-BS12.102.tif 509.351200 513.196671  1.007430 0.003800 -0.000115 1.050630


'''