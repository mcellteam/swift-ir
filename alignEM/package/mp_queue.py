#!/usr/bin/env python3

import multiprocessing as mp
# from multiprocessing import Queue
# from multiprocessing import JoinableQueue

# from multiprocessing import Pool
# import multiprocessing.process.AuthenticationString # <-- does not import
# import multiprocess as mp
# import multiprocess.context as ctx
import sys
import subprocess as sp
import inspect
import psutil
import time
from tqdm import tqdm
# import dill
# import pickle
import config as cfg
import package.em_utils as em
# from qtpy.QtCore import QThread
import logging
# from package.ui.TqdmToLogger import TqdmToLogger

__all__ = ['TaskQueue']

import logging
import time

import io

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
        # self.logger = logger
        self.logger = logger
        self.level = level or logging.INFO
    def write(self,buf):
        self.buf = buf.strip('\r\n\t ')
    def flush(self):
        # self.logger.log(self.level, self.buf)
        self.logger.log(self.level, self.buf)



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
  File "/Users/joelyancey/.local/share/virtualenvs/swift-ir-AuCIf4YN/lib/python3.9/site-packages/multiprocess/process.py", line 347, in __reduce__
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

# def log_subprocess_output(pipe):
#     for line in iter(pipe.readline, b''): # b'\n'-separated lines
#         logging.info('got line from subprocess: %r', line)

SENTINEL = 1
def worker(worker_id, task_q, result_q, n_tasks, n_workers, pbar_q = None):
    '''Function run by worker processes'''
    print('worker >>>>>>>>')
    time.sleep(.2)
    t_start = time.time()
    pbar_q.put(SENTINEL)

    for task_id, task in  iter(task_q.get, 'END_TASKS'):

        # print('worker_id %d    task_id %d    n_tasks %d    n_workers %d :' % (worker_id, task_id, n_tasks, n_workers))
        # print('task =\n', task)
        '''THIS IS THE FUNCTION CALL IN job_apply_affine.py (main):
        image_apply_affine(in_fn=in_fn, out_fn=out_fn, afm=afm, rect=rect, grayBorder=grayBorder)'''

        perc_complete = em.percentage(task_id, n_tasks)
        # sys.stderr.write('mp_queue.py | RunnableWorker %d:  Running Task %d\n' % (worker_id, task_id))
        # sys.stderr.write("Total complete: %s\n" % perc_complete)

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
            # sys.stderr.write('mp_queue.py | RunnableWorker %d:  Task %d Completed with RC %d\n' % (worker_id, task_id, rc))
        except:
            outs = ''
            errs = 'TaskQueue worker %d : task exception: %s' % (worker_id, str(sys.exc_info()[0]))
            print(errs)
            rc = 1
            em.print_exception()

        pbar_q.put(SENTINEL)
        dt = time.time() - t0
        result_q.put((task_id, outs, errs, rc, dt)) # put method uses block=True by default
        task_q.task_done()
    result_q.close()
    # result_q.join_thread()
    task_q.task_done()
    # task_q.close() #jy
    # time.sleep(1)
    # sys.stderr.write('<<<<<<<<  RunnableWorker %d Finished' % (worker_id))



# # def pbar_listener(pbar_q, n_tasks:int, progress_callback=None):
# def pbar_listener(pbar_q, n_tasks:int):
#     '''Pretty sure this is better off as a separate function, at least with multiprocessing'''
#     print('TaskQueue.pbar_listener (caller=%s, n_tasks=%d):' % (str(inspect.stack()[1].function), n_tasks))
#     # print('about to call self.progress_callback.emit(1)...')
#     # progress_callback.emit(1)
#     # log = logging.getLogger(__name__)
#     # log.setLevel(logging.INFO)
#     # log.addHandler(TqdmLoggingHandler())
#
#
#     logger = logging.getLogger(__name__)
#     logger.addHandler(cfg.main_window.hud.ha)
#     tqdm_out = TqdmToLogger(logger, level=logging.INFO)
#     pbar = tqdm(total = n_tasks, file=tqdm_out)
#
#
#     # pbar = tqdm(total = n_tasks)
#     # n = 0
#     # for item in iter(pbar_q.get, None):
#     for item in iter(pbar_q.get, None):
#         # print('TaskQueue.pbar_listener | n = ', n)
#         # n += 1
#         pbar.update()
#         # cfg.main_window.hud.post(str(n) + '%% Complete')
#         # if progress_callback is not None:
#         #     progress_callback.emit(n)
#     pbar.close()



# class TqdmLoggingHandler(logging.Handler):
#     def __init__(self, level=logging.NOTSET):
#         super().__init__(level)
#
#     def emit(self, record):
#         try:
#             msg = self.format(record)
#             tqdm.tqdm.write(msg)
#             self.flush()
#         except Exception:
#             self.handleError(record)

class TaskQueue:
    # def __init__(self, n_tasks, start_method='forkserver', progress_callback=None):
    def __init__(self, n_tasks, start_method='forkserver',logging_handler=None):
        self.start_method = start_method
        self.ctx = mp.get_context(self.start_method)
        self.task_dict = {}
        self.workers = []
        self.close_worker = False
        self.n_tasks = n_tasks
        # self.ctx = mp.get_context(self.start_method)
        if sys.version_info >= (3, 7):
            self.close_worker = True
        self.logging_handler = logging_handler

        mpl = mp.log_to_stderr()
        mpl.setLevel(logging.INFO)

        print('TaskQueue | INITIALIZATION')
        print('TaskQueue | self.start_method = ', self.start_method)
        print('TaskQueue | self.close_worker = ', self.close_worker)
        print('TaskQueue | self.n_tasks = ', self.n_tasks)
        print('TaskQueue | sys.version_info = ', sys.version_info)
        # self.progress_callback = progress_callback

        # logging.basicConfig(level=logging.INFO)

    def pbar_listener(self, pbar_q, n_tasks:int):

        # print('TaskQueue.pbar_listener (caller=%s, n_tasks=):' % (str(inspect.stack()[1].function, str(n_tasks))))
        # print('about to call self.progress_callback.emit(2)...')
        '''self.progress_callback has an identical location in memory'''
        # self.progress_callback.emit(2)
        pbar = tqdm(total = n_tasks)

        # logger = logging.getLogger("hud")
        # # logger.addHandler(cfg.main_window.hud.handler)
        # tqdm_out = TqdmToLogger(logger, level=logging.INFO)
        # pbar = tqdm(total=n_tasks, file=tqdm_out)

        n = 0
        for item in iter(pbar_q.get, None):
            # print('TaskQueue.pbar_listener | n = ', n)
            n += 1
            pbar.update()
            # if self.progress_callback is not None:
            # self.progress_callback.emit(n)
        pbar.close()

    def start(self, n_workers, retries=0) -> None:

        '''type(task_q)= <class 'multiprocessing.queues.JoinableQueue'>
           type(result_q)= <class 'multiprocessing.queues.Queue'>'''
        '''mp_queue.TaskQueue.start | type(self.progress_callback) =  <class 'PyQt5.QtCore.pyqtBoundSignal'>
        mp_queue.TaskQueue.start | str(self.progress_callback) =  <bound PYQT_SIGNAL progressSignal of WorkerSignals object at 0x186f84dc0>'''
        print('TaskQueue.start >>>>>>>>')
        print('TaskQueue.start | sys.getsizeof(self.task_dict) = ', sys.getsizeof(self.task_dict))
        # log = logging.getLogger('AlignEMLogger')
        # log.setLevel(logging.INFO)
        # log.addHandler(TqdmLoggingHandler())

        self.task_dict = {}
        self.task_id = 0
        self.retries = retries
        self.n_workers = n_workers
        self.work_queue = self.ctx.JoinableQueue()
        self.result_queue = self.ctx.Queue()
        self.pbar_q = self.ctx.Queue()
        cfg.main_window.hud.post('Using %d workers in parallel to process a batch of %d tasks' % (self.n_workers, self.n_tasks))
        # pbar_proc = QProcess(target=self.pbar_listener, args=(self.m.pbar_q, self.n_tasks))
        print('mp_queue.start | self.n_tasks = ', self.n_tasks)
        self.pbar_proc = self.ctx.Process(target=self.pbar_listener, args=(self.pbar_q, self.n_tasks, ))
        self.pbar_proc.start()
        cfg.main_window.hud.post('Running RunnableWorker Threads...')
        for i in range(self.n_workers):
            sys.stderr.write('Restarting RunnableWorker %d >>>>>>>>' % i)
            # p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers))
            p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, self.pbar_q, ))
            # p = QProcess('', [i, self.m.work_queue, self.m.result_queue, self.n_tasks, self.n_workers, self.m.pbar_q])
            self.workers.append(p)
            self.workers[i].start()
        print('<<<<<<<< Exiting TaskQueue.start')

    def restart(self) -> None:
        sys.stderr.write('TaskQueue.restart >>>>>>>>')
        cfg.main_window.hud.post('Restarting the Task Queue...')
        self.work_queue = self.ctx.JoinableQueue()
        self.result_queue = self.ctx.Queue()
        self.pbar_q = self.ctx.Queue()
        self.workers = []
        # pbar_proc = QProcess(target=self.pbar_listener, args=(self.m.pbar_q, self.n_tasks))
        self.pbar_proc = self.ctx.Process(target=self.pbar_listener, args=(self.pbar_q, self.n_tasks, ))
        self.pbar_proc.start()
        for i in range(self.n_workers):
            sys.stderr.write('Restarting RunnableWorker %d >>>>>>>>' % i)
            # p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers))
            p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue, self.n_tasks, self.n_workers, self.pbar_q, ))
            # p = QProcess('', [i, self.m.work_queue, self.m.result_queue, self.n_tasks, self.n_workers, self.m.pbar_q])
            self.workers.append(p)
            self.workers[i].start()
        sys.stderr.write('<<<<<<<<  TaskQueue.restart')

    def end_tasks(self) -> None:
        '''Tell child processes to stop'''
        print('TaskQueue.end_tasks >>>>>>>>')
        # cfg.main_window.hud.post('Cleaning up running tasks...')
        for i in range(self.n_workers):
            self.work_queue.put('END_TASKS')


        # for i in range(self.n_workers):
        #     worker_id, dt = self.result_queue.get()
        #     print('TaskQueue worker: %d  total time: %.2f' % (worker_id, dt))
        print('<<<<<<<< TaskQueue.end_tasks')

    def stop(self) -> None:
        '''Stop all workers'''
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
        # print("TaskQueue.requeue  >>>>>>>>")
        task = []
        task.append(self.task_dict[task_id]['cmd'])
        task.extend(self.task_dict[task_id]['args'])
        self.task_dict[task_id]['stdout'] = None
        self.task_dict[task_id]['stderr'] = None
        self.task_dict[task_id]['rc'] = None
        self.task_dict[task_id]['status'] = 'queued'
        self.task_dict[task_id]['retries'] += 1
        self.work_queue.put((task_id, task))
        # print("<<<<<<<<  TaskQueue.requeue")

    def clear_tasks(self) -> None:
        self.task_dict = {}
        self.task_id = 0

    # def count_tasks(self) -> int:
    #     '''This does not work. It would be nice if it did.'''
    #     return len(self.task_dict)

    def collect_results(self) -> None:

        '''Get results from tasks'''
        print("\nTaskQueue.collect_results  >>>>>>>>")
        # cfg.main_window.hud.post('Collecting Results...')
        n_pending = len(self.task_dict) # <-- # images in the stack
        print('TaskQueue | n_pending = %d' % n_pending)
        print('TaskQueue | self.retries = %d' % n_pending)
        retries_tot = 0
        # if n_pending == 0:
        #     print('TaskQueue.collect_results | No tasks to run - Returning')
        #     return
        # pbar = tqdm(total = n)
        # i=0
        while (retries_tot < self.retries + 1) and n_pending:
            # i+=1
            # pbar.update()
            # self.progress_callback.emit(int((i/n)*100))
            print('mp_queue.collect_results | n_pending = %d' % n_pending)
            self.end_tasks()
            self.work_queue.join()
            self.stop()
            retry_list = []
            # pbar_ = tqdm(total=self.n_tasks)
            for j in range(n_pending):
                # pbar_.update(1)
                # print('mp_queue | j = ', j)
                task_id, outs, errs, rc, dt = self.result_queue.get()
                # sys.stderr.write('Collected results from Task_ID %d\n' % (task_id))
                self.task_dict[task_id]['stdout'] = outs
                self.task_dict[task_id]['stderr'] = errs
                self.task_dict[task_id]['rc'] = rc
                if rc == 0:
                    self.task_dict[task_id]['status'] = 'completed'
                else:
                    self.task_dict[task_id]['status'] = 'task_error'
                    retry_list.append(task_id)
                self.task_dict[task_id]['dt'] = dt
            '''Restart Queue and Requeue failed tasks'''
            n_pending = len(retry_list)
            if (retries_tot < self.retries) and n_pending:
                sys.stderr.write('mp_queue | Requeuing Any Failed Tasks...')
                sys.stderr.write('mp_queue | Failed Tasks: %d' % n_pending)
                sys.stderr.write('mp_queue |     Task IDs: %s' % str(retry_list))

                self.restart()
                for task_id in retry_list:
                    sys.stderr.write('mp_queue | Requeuing Failed Task ID: %d   Retries: %d' % (task_id, retries_tot + 1))
                    # sys.stderr.write('mp_queue |                     Task: %s' % (str(self.task_dict[task_id])))
                    # [print(key,':',value) for key, value in self.task_dict[task_id].items()]
                    self.requeue_task(task_id)
            retries_tot += 1
        sys.stderr.write('    Finished Collecting Results for %d Tasks\n' % (len(self.task_dict)))
        sys.stderr.write('    Failed Tasks: %d\n' % (n_pending))
        sys.stderr.write('    Retries: %d\n\n' % (retries_tot - 1))
        if n_pending == 0:
            print('Failed Tasks   : %d' % n_pending)
            print('Retries        : %d' % (retries_tot - 1))
        else:
            print('Failed Tasks: %d' % n_pending, logging.WARNING)
            print('Retries        : %d' % (retries_tot - 1), logging.WARNING)

        print('<<<<<<<<  TaskQueue.collect_results')



# def main(args):
#     parser = argparse.ArgumentParser(description="Do something.")
#     parser.add_argument("-x", "--xcenter", type=float, default= 2, required=False)
#     parser.add_argument("-y", "--ycenter", type=float, default= 4, required=False)
#     args = parser.parse_args(args)
# https://stackoverflow.com/questions/14500183/in-python-can-i-call-the-main-of-an-imported-module
if __name__ == '__main__':
    print('mp_queue.__main__ >>>>>>>>')
    print("Running " + __file__ + ".__main__()")

    # mp.freeze_support()
    tq = TaskQueue()
    cpus = psutil.cpu_count(logical=False)
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

    print('<<<<<<<< mp_queue.__main__')

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
########################################################################################################################

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
task= ['/Users/joelyancey/.local/share/virtualenvs/swift-ir-AuCIf4YN/bin/python3', 
       '/Users/joelyancey/glanceem_swift/swift-ir/source/alignEM/package/job_apply_affine.py', 
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
task = ['/Users/joelyancey/glanceem_swift/swift-ir/source/alignEM/package//lib/bin_darwin/iscale2', 
        '+4', 
        'of=/Users/joelyancey/glanceem_swift/test_projects/test16/scale_4/img_src/R34CA1-BS12.117.tif', 
        '/Users/joelyancey/glanceem_swift/test_projects/test16/scale_1/img_src/R34CA1-BS12.117.tif']

'''


#------------------------------------------------------
'''
PROBLEMATIC
INFO:interface:
Task Error:
INFO:interface:   CMD:    /Users/joelyancey/.local/share/virtualenvs/swift-ir-AuCIf4YN/bin/python3
INFO:interface:   ARGS:   ['/Users/joelyancey/glanceem_swift/swift-ir/source/alignEM/package/job_single_alignment.py', '/Users/joelyancey/glanceEM_SWiFT/test_projects/full_volume_josef_2/project_runner_job_file.json', 'init_affine', '4', 'c', '127', '1', '1']
INFO:interface:   STDERR: /Users/joelyancey/.local/share/virtualenvs/swift-ir-AuCIf4YN/bin/python3: can't open file '/Users/joelyancey/glanceem_swift/swift-ir/source/alignEM/package/job_single_alignment.py': [Errno 2] No such file or directory







WHAT A *GOOD* single_alignment_job run looks like:
project_runner.do_alignment | Starting mp_queue with args:
  /Users/joelyancey/.local/share/virtualenvs/swift-ir-AuCIf4YN/bin/python3
  /Users/joelyancey/Downloads/swift-ir-joel-dev-pyside6/source/alignEM/package/job_single_alignment.py
  /Users/joelyancey/glanceem_swift/test_projects/test_last_push/project_runner_job_file.json
  init_affine
  4
  c
  9
  1
  0

HOW IS ^^ THAT DIFFERENT FROM THIS:
Starting mp_queue with args:
  /Users/joelyancey/.local/share/virtualenvs/swift-ir-AuCIf4YN/bin/python3
  /Users/joelyancey/glanceem_swift/swift-ir/source/alignEM/package/src/job_single_alignment.py
  /Users/joelyancey/glanceEM_SWiFT/test_projects/test94/project_runner_job_file.json
  init_affine
  4
  c
  14
  1
  0



'''








# ^^^^^^^^^^^^^ THE FURTHER ALONG ONE ^^^^^^^^^^^^^^^^^^^^^

























# #!/usr/bin/env python3
#
# import sys
# import multiprocessing as mp
# from multiprocessing import Pool
# import subprocess as sp
# import psutil
# import time
# from tqdm import tqdm
#
# print_switch = 1
#
# #
# # Function run by worker processes
# #
# def worker(worker_id, task_q, result_q):
#     t_start = time.time()
#     # type(task_q.get) =  <class 'method'>
#
#     # for task_id, task in tqdm(iter(task_q.get, 'END_TASKS')):
#     for task_id, task in iter(task_q.get, 'END_TASKS'):
#         if print_switch:
#             sys.stderr.write('mp_queue.py | RunnableWorker %d:  Running Task %d\n' % (worker_id, task_id))
#         t0 = time.time()
#         outs = ''
#         errs = ''
#         rc = 1
#         try:
#             task_proc = sp.Popen(task, bufsize=-1, shell=False, stdout=sp.PIPE, stderr=sp.PIPE)
#
#             outs, errs = task_proc.communicate()
#
#             outs = '' if outs == None else outs.decode('utf-8')
#             errs = '' if errs == None else errs.decode('utf-8')
#             rc = task_proc.returncode
#             if print_switch:
#                 sys.stderr.write('mp_queue.py | RunnableWorker %d:  Task %d Completed with RC %d\n' % (worker_id, task_id, rc))
#         except:
#
#             outs = ''
#             errs = 'TaskQueue worker %d : task exception: %s' % (worker_id, str(sys.exc_info()[0]))
#             print(errs)
#             rc = 1
#
#         dt = time.time() - t0
#         result_q.put((task_id, outs, errs, rc, dt))
#         task_q.task_done()
#
#     result_q.close()
#     # result_q.join_thread()
#     sys.stderr.write('RunnableWorker %d:  Stopping\n' % (worker_id))
#     task_q.task_done()
#
#
# #  t_stop = time.time()
# #  dt = t_stop - t_start
# #  result_q.put((worker_id, dt))
#
# class TaskQueue:
#
#     def __init__(self, start_method='forkserver'):
#         self.start_method = start_method
#         self.ctx = mp.get_context(self.start_method)
#         self.workers = []
#         self.close_worker = False
#         if sys.version_info >= (3, 7):
#             self.close_worker = True
#
#     def start(self, n_workers, retries=10):
#         self.work_queue = self.ctx.JoinableQueue()
#         self.result_queue = self.ctx.Queue()
#         self.task_dict = {}
#         self.task_id = 0
#         self.retries = retries
#
#         self.n_workers = n_workers
#         for i in range(self.n_workers):
#             p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue))
#             self.workers.append(p)
#             self.workers[i].start()
#
#     def restart(self):
#         sys.stderr.write('\nmp_queue.py | Restarting Task Queue...\n')
#         self.work_queue = self.ctx.JoinableQueue()
#         self.result_queue = self.ctx.Queue()
#         self.workers = []
#
#         for i in range(self.n_workers):
#             sys.stderr.write('    Restarting RunnableWorker %d\n' % (i))
#             p = self.ctx.Process(target=worker, args=(i, self.work_queue, self.result_queue))
#             self.workers.append(p)
#             self.workers[i].start()
#         sys.stderr.write('    Done Restarting Task Queue\n')
#
#     def end_tasks(self):
#         # Tell child processes to stop
#         for i in range(self.n_workers):
#             self.work_queue.put('END_TASKS')
#
#     #    for i in range(self.n_workers):
#     #        worker_id, dt = self.result_queue.get()
#     #        print('TaskQueue worker: %d  total time: %.2f' % (worker_id, dt))
#
#     # Stop all workers
#     def stop(self):
#         self.work_queue.close()
#         time.sleep(0.1)  # Needed to Avoid Race Condition
#
#     #    for i in range(len(self.workers)):
#     #      if self.close_worker:
#     #        self.workers[i].close()
#     #      else:
#     #        self.workers[i].terminate()
#
#     def add_task(self, task):
#         self.task_dict[self.task_id] = {}
#         self.task_dict[self.task_id]['cmd'] = task[0]
#         self.task_dict[self.task_id]['args'] = task[1:]
#         self.task_dict[self.task_id]['stdout'] = None
#         self.task_dict[self.task_id]['stderr'] = None
#         self.task_dict[self.task_id]['rc'] = None
#         self.task_dict[self.task_id]['status'] = 'queued'
#         self.task_dict[self.task_id]['retries'] = 0
#         self.work_queue.put((self.task_id, task))
#         self.task_id += 1
#
#     def requeue_task(self, task_id):
#         task = []
#         task.append(self.task_dict[task_id]['cmd'])
#         task.extend(self.task_dict[task_id]['args'])
#         self.task_dict[task_id]['stdout'] = None
#         self.task_dict[task_id]['stderr'] = None
#         self.task_dict[task_id]['rc'] = None
#         self.task_dict[task_id]['status'] = 'queued'
#         self.task_dict[task_id]['retries'] += 1
#         self.work_queue.put((task_id, task))
#
#     def clear_tasks(self):
#         self.task_dict = {}
#         self.task_id = 0
#
#     def collect_results(self):
#
#         n_pending = len(self.task_dict)
#         retries_tot = 0
#         while (retries_tot < self.retries + 1) and n_pending:
#
#             self.end_tasks()
#             self.work_queue.join()
#             self.stop()
#
#             #     Get results from tasks
#             retry_list = []
#             for j in range(n_pending):
#                 task_id, outs, errs, rc, dt = self.result_queue.get()
#                 #        sys.stderr.write('Collected results from Task_ID %d\n' % (task_id))
#                 self.task_dict[task_id]['stdout'] = outs
#                 self.task_dict[task_id]['stderr'] = errs
#                 self.task_dict[task_id]['rc'] = rc
#                 if rc == 0:
#                     self.task_dict[task_id]['status'] = 'completed'
#                 else:
#                     self.task_dict[task_id]['status'] = 'task_error'
#                     retry_list.append(task_id)
#                 self.task_dict[task_id]['dt'] = dt
#
#             #     Restart Queue and Requeue failed tasks
#             n_pending = len(retry_list)
#             if (retries_tot < self.retries) and n_pending:
#                 sys.stderr.write('\nNeed to Requeue %d Failed Tasks...\n' % (n_pending))
#                 sys.stderr.write('    Task_IDs: %s\n' % (str(retry_list)))
#                 self.restart()
#                 for task_id in retry_list:
#                     sys.stderr.write('mp_queue | Requeuing Failed Task_ID: %d   Retries: %d\n' % (task_id, retries_tot + 1))
#                     # sys.stderr.write('  Task: %s\n' % (str(self.task_dict[task_id])))
#                     [print(key,':',value) for key, value in self.task_dict[task_id].items()]
#                     self.requeue_task(task_id)
#             retries_tot += 1
#
#         sys.stderr.write('\nFinished Collecting Results for %d Tasks\n' % (len(self.task_dict)))
#         sys.stderr.write('    Failed Tasks: %d\n' % (n_pending))
#         sys.stderr.write('    Retries: %d\n\n' % (retries_tot - 1))
#
#
# if __name__ == '__main__':
#     print("Running " + __file__ + ".__main__()")
#     # mp.freeze_support()
#     tq = TaskQueue()
#     cpus = psutil.cpu_count(logical=False)
#     cpus = 8
#     tq.start(cpus)
#
#     tasks = []
#     #    tasks.append(['ls','./'])
#     #    tasks.append(['ls','../'])
#     #    tasks.append(['echo','\n>>>>>> hello world!!! <<<<<<\n'])
#
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda3/'])
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])
#     #    tasks.append(['ls','-C', '-F', '-R', '/anaconda4/'])
#
#     for i in range(2 * cpus):
#         tasks.append(['./demo_datamodel_read.py'])
#
#     print('\n>>>>>> Submitting Tasks: <<<<<<\n')
#     for task in tasks:
#         tq.add_task(task)
#
#     print('\n>>>>>> Collecting Results: <<<<<<\n')
#     tq.collect_results()
#
#     print('\n>>>>>> Task Results: <<<<<<\n')
#     for task_id in tq.task_dict:
#         print('[task %s]: %s %s %s %s %s' %
#               (str(task_id),
#                str(tq.task_dict[task_id]['cmd']),
#                str(tq.task_dict[task_id]['args']),
#                str(tq.task_dict[task_id]['rc']),
#                str(tq.task_dict[task_id]['status']),
#                str(tq.task_dict[task_id]['dt'])))
#
#         print('\n%s\n' % (tq.task_dict[task_id]['stdout']))
#
#     '''
#     tq.start(cpus)
#
#     print('\n>>>>>> Submitting Tasks Again: <<<<<<\n')
#     for task in tasks:
#       tq.add_task(task)
#
#     print('\n>>>>>> Collecting Results Again: <<<<<<\n')
#     tq.collect_results()
#
#     print('\n>>>>>> More Task Results: <<<<<<\n')
#     for task_id in tq.task_dict:
#         print( '[task %s]: %s %s %s %s %s' %
#                (str(task_id),
#                str(tq.task_dict[task_id]['cmd']),
#                str(tq.task_dict[task_id]['args']),
#                str(tq.task_dict[task_id]['rc']),
#                str(tq.task_dict[task_id]['status']),
#                str(tq.task_dict[task_id]['dt']) ))
#
#         print('\n%s\n' % (tq.task_dict[task_id]['stdout']))
#     '''
