# Copyright (c) 2012 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   February 29, 2012


"""
 This is a thread module for blade which is used to spawn
 threads to finish some kind of work.

"""


import Queue
import subprocess
import sys
import threading
import time
import traceback

import blade_util
import configparse
import console


signal_map = {-1: 'SIGHUP', -2: 'SIGINT', -3: 'SIGQUIT',
              -4: 'SIGILL', -5: 'SIGTRAP', -6: 'SIGABRT',
              -7: 'SIGBUS', -8: 'SIGFPE', -9: 'SIGKILL',
              -10: 'SIGUSR1', -11: 'SIGSEGV', -12: 'SIGUSR2',
              -13: 'SIGPIPE', -14: 'SIGALRM', -15: 'SIGTERM',
              -17: 'SIGCHLD', -18: 'SIGCONT', -19: 'SIGSTOP',
              -20: 'SIGTSTP', -21: 'SIGTTIN', -22: 'SIGTTOU',
              -23: 'SIGURG', -24: 'SIGXCPU', -25: 'SIGXFSZ',
              -26: 'SIGVTALRM', -27: 'SIGPROF', -28: 'SIGWINCH',
              -29: 'SIGIO', -30: 'SIGPWR', -31: 'SIGSYS'}


class WorkerThread(threading.Thread):
    def __init__(self, id, job_queue, job_handler, redirect):
        """Init methods for this thread. """
        threading.Thread.__init__(self)
        self.thread_id = id
        self.job_queue = job_queue
        self.job_handler = job_handler
        self.redirect = redirect
        self.job_start_time, self.job_timeout = 0, 0
        self.job_process = None
        self.job_name = ''
        self.job_is_timeout = False
        self.job_lock = threading.Lock()
        console.info('blade test executor %d starts to work' % self.thread_id)

    def __process(self):
        """Private handler to handle one job. """
        console.info('blade worker %d starts to process' % self.thread_id)
        console.info('blade worker %d finish' % self.thread_id)

    def cleanup_job(self):
        """Clean up job data. """
        self.job_start_time, self.job_timeout = 0, 0
        self.job_process = None
        self.job_name = ''
        self.job_is_timeout = False

    def set_job_data(self, p, name, timeout):
        """Set the popen object and name if the job is run in a subprocess. """
        self.job_process, self.job_name, self.job_timeout = p, name, timeout

    def check_job_timeout(self, now):
        """Check whether the job is timeout or not.

        This method simply checks job timeout and returns immediately.
        The caller should invoke this method repeatedly so that a job
        which takes a very long time would be timeout sooner or later.
        """
        try:
            self.job_lock.acquire()
            if (not self.job_is_timeout and self.job_start_time and
                self.job_timeout is not None and
                self.job_name and self.job_process is not None):
                if self.job_start_time + self.job_timeout < now:
                    self.job_is_timeout = True
                    console.error('%s: TIMEOUT\n' % self.job_name)
                    self.job_process.terminate()
        finally:
            self.job_lock.release()

    def run(self):
        """executes and runs here. """
        try:
            if self.job_handler:
                job_queue = self.job_queue
                while not job_queue.empty():
                    try:
                        job = job_queue.get_nowait()
                    except Queue.Empty:
                        continue
                    self.job_start_time = time.time()
                    self.job_handler(job, self.redirect, self)
                    try:
                        self.job_lock.acquire()
                        self.cleanup_job()
                    finally:
                        self.job_lock.release()
            else:
                self.__process()
        except:
            traceback.print_exc()


class TestScheduler(object):
    """TestScheduler. """
    def __init__(self, tests_list, jobs, tests_run_map):
        """init method. """
        self.tests_list = tests_list
        self.jobs = jobs
        self.tests_run_map = tests_run_map
        self.tests_run_map_lock = threading.Lock()
        self.cpu_core_num = blade_util.cpu_count()
        self.num_of_tests = len(self.tests_list)
        self.max_worker_threads = 16
        self.failed_targets = []
        self.failed_targets_lock = threading.Lock()
        self.num_of_run_tests = 0
        self.num_of_run_tests_lock = threading.Lock()
        self.job_queue = Queue.Queue(0)
        self.exclusive_job_queue = Queue.Queue(0)

    def __get_workers_num(self):
        """get the number of thread workers. """
        max_workers = max(self.cpu_core_num, self.max_worker_threads)
        if self.jobs <= 1:
            return 1
        elif self.jobs > max_workers:
            self.jobs = max_workers

        return min(self.num_of_tests, self.jobs)

    def __get_result(self, returncode):
        """translate result from returncode. """
        result = 'SUCCESS'
        if returncode:
            result = signal_map.get(returncode, 'FAILED')
            result = '%s:%s' % (result, returncode)
        return result

    def _run_job_redirect(self, job, job_thread):
        """run job and redirect the output. """
        target, run_dir, test_env, cmd = job
        test_name = target.fullname
        shell = target.data.get('run_in_shell', False)
        if shell:
            cmd = subprocess.list2cmdline(cmd)
        timeout = target.data.get('test_timeout')
        console.info('Running %s' % cmd)
        p = subprocess.Popen(cmd,
                             env=test_env,
                             cwd=run_dir,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             close_fds=True,
                             shell=shell)
        job_thread.set_job_data(p, test_name, timeout)

        stdout = p.communicate()[0]
        result = self.__get_result(p.returncode)
        console.info('Output of %s:\n%s\n%s finished: %s\n' % (
                     test_name, stdout, test_name, result))

        return p.returncode

    def _run_job(self, job, job_thread):
        """run job, do not redirect the output. """
        target, run_dir, test_env, cmd = job
        test_name = target.fullname
        shell = target.data.get('run_in_shell', False)
        if shell:
            cmd = subprocess.list2cmdline(cmd)
        timeout = target.data.get('test_timeout')
        console.info('Running %s' % cmd)
        p = subprocess.Popen(cmd, env=test_env, cwd=run_dir, close_fds=True, shell=shell)
        job_thread.set_job_data(p, test_name, timeout)
        p.wait()
        result = self.__get_result(p.returncode)
        console.info('%s finished : %s\n' % (test_name, result))

        return p.returncode

    def _process_job(self, job, redirect, job_thread):
        """process routine.

        Each test is a tuple (target, run_dir, env, cmd)

        """
        target = job[0]
        start_time = time.time()

        try:
            if redirect:
                returncode = self._run_job_redirect(job, job_thread)
            else:
                returncode = self._run_job(job, job_thread)
        except OSError, e:
            console.error('%s: Create test process error: %s' %
                          (target.fullname, str(e)))
            returncode = 255

        costtime = time.time() - start_time

        if returncode:
            target.data['test_exit_code'] = returncode
            self.failed_targets_lock.acquire()
            self.failed_targets.append(target)
            self.failed_targets_lock.release()

        self.tests_run_map_lock.acquire()
        run_item_map = self.tests_run_map.get(target.key, {})
        if run_item_map:
            run_item_map['result'] = self.__get_result(returncode)
            run_item_map['costtime'] = costtime
        self.tests_run_map_lock.release()

        self.num_of_run_tests_lock.acquire()
        self.num_of_run_tests += 1
        self.num_of_run_tests_lock.release()

    def print_summary(self):
        """print the summary output of tests. """
        console.info('There are %d tests scheduled to run by scheduler' % (len(self.tests_list)))

    def _join_thread(self, t):
        """Join thread and keep signal awareable"""
        # The Thread.join without timeout will block signals, which makes
        # blade can't be terminated by Ctrl-C
        while t.isAlive():
            t.join(1)

    def _wait_worker_threads(self, threads):
        """Wait for worker threads to complete. """
        config = configparse.blade_config.get_config('global_config')
        test_timeout = config['test_timeout']
        while threads:
            time.sleep(1)  # Check every second
            now = time.time()
            dead_threads = []
            for t in threads:
                if t.isAlive():
                    if test_timeout is not None:
                        t.check_job_timeout(now)
                else:
                    dead_threads.append(t)

            for dt in dead_threads:
                threads.remove(dt)

    def schedule_jobs(self):
        """scheduler. """
        if self.num_of_tests <= 0:
            return

        num_of_workers = self.__get_workers_num()
        console.info('spawn %d worker(s) to run tests' % num_of_workers)

        for i in self.tests_list:
            target = i[0]
            if target.data.get('exclusive'):
                self.exclusive_job_queue.put(i)
            else:
                self.job_queue.put(i)

        redirect = num_of_workers > 1
        threads = []
        for i in range(num_of_workers):
            t = WorkerThread(i, self.job_queue, self._process_job, redirect)
            t.start()
            threads.append(t)
        self._wait_worker_threads(threads)

        if not self.exclusive_job_queue.empty():
            console.info('spawn 1 worker to run exclusive tests')
            last_t = WorkerThread(num_of_workers, self.exclusive_job_queue,
                                  self._process_job, False)
            last_t.start()
            self._wait_worker_threads([last_t])

        self.print_summary()
