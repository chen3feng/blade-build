"""

 Copyright (c) 2012 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   February 29, 2012

 This is a thread module for blade which is used to spawn
 threads to finish some kind of work.

"""


import multiprocessing
import Queue
import subprocess
import sys
import threading
import time
import traceback
from blade_util import info
from blade_util import info_str


signal_map = { -1 : 'SIGHUP', -2 : 'SIGINT', -3 : 'SIGQUIT',
               -4 : 'SIGILL', -5 : 'SIGTRAP', -6 : 'SIGABRT',
               -7 : 'SIGBUS', -8 : 'SIGFPE', -9 : 'SIGKILL',
               -10 : 'SIGUSR1', -11 : 'SIGSEGV', -12 : 'SIGUSR2',
               -13 : 'SIGPIPE', -14 : 'SIGALRM', -15 : 'SIGTERM',
               -17 : 'SIGCHLD', -18 : 'SIGCONT', -19 : 'SIGSTOP',
               -20 : 'SIGTSTP', -21 : 'SIGTTIN', -22 : 'SIGTTOU',
               -23 : 'SIGURG', -24 : 'SIGXCPU', -25 : 'SIGXFSZ',
               -26 : 'SIGVTALRM', -27 : 'SIGPROF', -28 : 'SIGWINCH',
               -29 : 'SIGIO', -30 : 'SIGPWR', -31 : 'SIGSYS'}


class WorkerThread(threading.Thread):
    def __init__(self, worker_args, proc_func, args):
        """Init methods for this thread. """
        threading.Thread.__init__(self)
        self.worker_args = worker_args
        self.func_args = args
        self.job_handler = proc_func
        self.thread_id = int(self.worker_args)
        self.start_working_time = time.time()
        self.end_working_time = None
        self.ret = None
        info("blade test executor %d starts to work" % self.thread_id)

    def __process(self):
        """Private handler to handle one job. """
        info("blade worker %d starts to process" % self.thread_id)
        info("blade worker %d finish" % self.thread_id)
        return

    def get_return(self):
        """returns worker result to caller. """
        return self.ret

    def run(self):
        """executes and runs here. """
        try:
            if self.job_handler:
                self.ret = self.job_handler(*self.func_args)
                self.end_working_time = time.time()
                return True
            else:
                self.__process()
                return True
        except:
            (ErrorType, ErrorValue, ErrorTB) = sys.exc_info()
            print sys.exc_info()
            traceback.print_exc(ErrorTB)


class TestScheduler(object):
    """TestScheduler. """
    def __init__(self, tests_list, jobs, tests_run_map):
        """init method. """
        self.tests_list = tests_list
        self.jobs = jobs
        self.tests_run_map = tests_run_map
        self.tests_run_map_lock = threading.Lock()
        self.worker_threads = []
        self.cpu_core_num = multiprocessing.cpu_count()
        self.num_of_tests = len(self.tests_list)
        self.max_worker_threads = 16
        self.threads = []
        self.tests_stdout_map = {}
        self.failed_targets = []
        self.failed_targets_lock = threading.Lock()
        self.tests_stdout_lock = threading.Lock()
        self.num_of_run_tests = 0
        self.num_of_run_tests_lock = threading.Lock()
        self.job_queue = Queue.Queue(0)
        self.exclusive_job_queue = Queue.Queue(0)

    def __get_workers_num(self):
        """get the number of thread workers. """
        max_workers = max([self.cpu_core_num, self.max_worker_threads])
        if max_workers == 0:
            max_workers = self.max_worker_threads

        if self.jobs <= 1:
            return 1
        elif self.jobs > max_workers:
            self.jobs = max_workers

        if self.num_of_tests <= self.jobs:
            return self.num_of_tests
        else:
            return self.jobs

        return 1

    def __get_result(self, returncode):
        """translate result from returncode. """
        result = 'SUCCESS'
        if returncode:
            result = signal_map.get(returncode, 'FAILED')
        return result

    def _run_job_redirect(self, job):
        """run job, redirect the output. """
        (target, run_dir, test_env, cmd) = job
        test_name = "%s/%s" % (target['path'], target['name'])

        info("Running %s" % test_name)
        start_time = time.time()
        p = subprocess.Popen(cmd,
                             env=test_env,
                             cwd=run_dir,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             shell=True)

        (stdoutdata, stderrdata) = p.communicate()
        cost_time = time.time() - start_time
        result = self.__get_result(p.returncode)
        print "%s\n%s%s\n" % (info_str("Output of %s" % test_name),
                stdoutdata, info_str("%s finished: %s" % (test_name, result)))

        return (target, p.returncode, cost_time)

    def _run_job(self, job):
        """run job, do not redirect the output. """
        (target, run_dir, test_env, cmd) = job
        info("Running %s/%s" % (target['path'], target['name']))

        start_time = time.time()
        p = subprocess.Popen(cmd,
                             env=test_env,
                             cwd=run_dir,
                             shell=True)

        p.wait()
        cost_time = time.time() - start_time
        result = self.__get_result(p.returncode)
        info("%s/%s finished : %s\n" % (
             target['path'], target['name'], result))

        return (target, p.returncode, cost_time)

    def _process_command(self, job_queue, redirect):
        """process routine.

        Each test is a tuple (target, run_dir, env, cmd)

        """
        while not job_queue.empty():
            if redirect:
                (target,
                 returncode,
                 costtime) = self._run_job_redirect(job_queue.get())
            else:
                (target,
                 returncode,
                 costtime) = self._run_job(job_queue.get())

            if returncode:
                target["test_exit_code"] = returncode
                self.failed_targets_lock.acquire()
                self.failed_targets.append(target)
                self.failed_targets_lock.release()

            self.tests_run_map_lock.acquire()
            target_key = "%s:%s" % (target['path'], target['name'])
            run_item_map = self.tests_run_map.get(target_key, {})
            if run_item_map:
                run_item_map['result'] = self.__get_result(returncode)
                run_item_map['costtime'] = costtime
            self.tests_run_map_lock.release()

            self.num_of_run_tests_lock.acquire()
            self.num_of_run_tests += 1
            self.num_of_run_tests_lock.release()
        return True

    def print_summary(self):
        """print the summary output of tests. """
        info("There are %d tests scheduled to run by scheduler" % (len(self.tests_list)))

    def schedule_jobs(self):
        """scheduler. """
        if self.num_of_tests <= 0:
            return True

        num_of_workers = self.__get_workers_num()
        info("spawn %d worker(s) to run tests" % num_of_workers)

        for i in self.tests_list:
            target = i[0]
            if target.get('options', {}).get('exclusive', False):
                self.exclusive_job_queue.put(i)
            else:
                self.job_queue.put(i)

        test_arg = [self.job_queue, num_of_workers > 1]
        for i in range(num_of_workers):
            t = WorkerThread((i), self._process_command, args=test_arg)
            t.start()
            self.threads.append(t)
        for t in self.threads:
            t.join()

        if not self.exclusive_job_queue.empty():
            info("spawn 1 worker to run exclusive tests")
            test_arg = [self.exclusive_job_queue, False]
            last_t = WorkerThread((num_of_workers), self._process_command, args=test_arg)
            last_t.start()
            last_t.join()

        self.print_summary()
        return True
