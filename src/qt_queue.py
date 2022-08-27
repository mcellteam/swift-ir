#!/usr/bin/env python3

'''

QThread isn’t a thread itself.
It’s a wrapper around an operating system thread.
The real thread object is created when you call ***QThread.start()***

Like with any other threading solutions,
with QThread you must protect your data and resources from concurrent, or simultaneous, access.

A thread-safe object is an object that can be accessed concurrently by multiple threads
and is guaranteed to be in a valid state.


multiprocessing and GUI updating - Qprocess or multiprocessing?
https://stackoverflow.com/questions/15675043/multiprocessing-and-gui-updating-qprocess-or-multiprocessing

"Note that we only need a single QThread to control several multiprocesses."
https://elsampsa.github.io/valkka-examples/_build/html/qt_notes.html

Qt main loop running with signals and slots
    |
    +--- QThread receiving/sending signals --- writing/reading communication pipes
         ==> use an instance of QValkkaThread                        |
                                                       +-------------+------+----------------+
                                                       |                    |                |
                                                      multiprocess_1   multiprocess_2  multiprocess_3

                                                       python multiprocesses doing their thing
                                                       and writing/reading their communication pipes
                                                       ==> subclass from valkka.multiprocess.MessageProcess

+--------------------------------------+
|                                      |
| QThread                              |
|  watching the communication pipe     |
|                   +----- reads "ping"|
|                   |               |  |
+-------------------|------------------+
                    |               |
 +------------------|-------+       |        ...
 | Frontend methods |       |       ^          :
 |                  |       |      pipe        :
 | def ping():  <---+       |       |          :
 |   do something           |       |          :
 |   (say, send a qt signal)|       |          :
 |                          |       |          :
 | def pong(): # qt slot    |       |          :
 |   sendSignal("pong") ---------+  |          :
 |                          |    |  |          :    valkka.multiprocess.MessageProcess
 +--------------------------+    |  |          :
 | Backend methods          |    |  |          :    Backend is running in the "background" in its own virtual memory space
 |                          |    |  |          :
 | sendSignal__("ping") ------->----+          :
 |                          |    |             :
 | watching childpipe <------- childpipe       :
 |                 |        |                  :
 | def pong__(): <-+        |                  :
 |  do something            |                  :
 |                          |                  :
 +--------------------------+                ..:

'''

import io
import sys
import time
import psutil
import logging
from tqdm import tqdm
import subprocess as sp
import multiprocessing as mp
from multiprocessing import Process, Queue
from qtpy.QtCore import Signal, QObject, QThread
try:     import src.config as cfg
except:  import config as cfg


'''SWIM/MIR:
stdout <- result
stderr <- info + errors
'''
__all__ = ['TaskRunner']


mpl = mp.log_to_stderr()
mpl.setLevel(logging.CRITICAL)


SENTINEL = 1
def worker(queue, worker_id, task_q, result_q, n_tasks, n_workers):
    '''Function run by worker processes'''

    time.sleep(.1)

    for task_id, task in iter(task_q.get, 'END_TASKS'):

        logger.debug('worker_id %d    task_id %d    n_tasks %d    n_workers %d :' % (worker_id, task_id, n_tasks, n_workers))
        logger.debug('task: %s' % str(task))
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
        # queue.put("done")
        dt = time.time() - t0
        result_q.put((task_id, outs, errs, rc, dt)) # put method uses block=True by default
        task_q.task_done()

    result_q.close()
    # result_q.join_thread()
    task_q.task_done()
    # task_q.close() #jy
    queue.put("done")
    logger.debug('<<<< Worker %d Finished' % (worker_id))


# Things below live on the main thread
def run_job(self, input):
    """ Call this to start a new job """
    self.runner.job_input = input
    self.runner_thread.start()

def handle_msg(self, msg):
    cfg.main_window.hud.post(msg)
    if msg == 'done':
        self.runner_thread.quit()
        self.runner_thread.wait()

class TaskRunner(QObject):
    """
    Runs a job in a separate process and forwards messages from the job to the
    main thread through a pyqtSignal.
    """
    msg_from_job = Signal(object)

    def __init__(self, n_tasks, start_signal):
        self.start_method = 'forkserver'
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
        self.tqdm_desc = ''
        super(TaskRunner).__init__()
        self.job_input = None
        start_signal.connect(self._run) # SIGNAL TO START THE JOB

    def _run(self):
        queue = Queue()
        # p = Process(target=job_function, args=(queue, self.job_input))
        # p.start()

        # p = self.ctx.Process(target=worker, args=(queue,
        #                                           self.job_input[0],
        #                                           self.job_input[1],
        #                                           self.job_input[2],
        #                                           self.job_input[3],
        #                                           self.job_input[4],
        #                                           self.job_input[5],
        #                                           )
        #                      )
        p = self.ctx.Process(target=worker, args=(queue, *self.job_input))
        self.workers.append(p)
        p.start()

        while True:
            msg = queue.get()
            self.msg_from_job.emit(msg)
            if msg == 'done':
                break

