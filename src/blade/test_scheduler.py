# Copyright (c) 2012 Tencent Inc.
# All rights reserved.
#
# Author: Michaelpeng <michaelpeng@tencent.com>
# Date:   February 29, 2012


"""
 This is a thread module for blade which is used to spawn
 threads to finish some kind of work.

"""


from collections import namedtuple
import Queue
import signal
import subprocess
import threading
import time
import traceback

import blade_util
import config
import console


TestRunResult = namedtuple('TestRunResult', ['exit_code', 'start_time', 'cost_time'])


# dict{-signo : signame}
_SIGNAL_MAP = dict([
    (-getattr(signal, name), name) for name in dir(signal)
    if name.startswith('SIG') and not name.startswith('SIG_')
])


class WorkerThread(threading.Thread):
    def __init__(self, id, job_queue, job_handler, redirect):
        """Init methods for this thread. """
        threading.Thread.__init__(self)
        self.thread_id = id
        self.running = True
        self.job_queue = job_queue
        self.job_handler = job_handler
        self.redirect = redirect
        self.job_start_time, self.job_timeout = 0, 0
        self.job_process = None
        self.job_name = ''
        self.job_is_timeout = False
        self.job_lock = threading.Lock()
        console.info('blade test executor %d starts to work' % self.thread_id)

    def _process(self):
        """Private handler to handle one job. """
        console.info('blade worker %d starts to process' % self.thread_id)
        console.info('blade worker %d finish' % self.thread_id)

    def terminate(self):
        """Terminate the worker. """
        self.running = False

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
                while not job_queue.empty() and self.running:
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
                self._process()
        except:  # pylint: disable=bare-except
            traceback.print_exc()


_MAX_WORKER_THREADS = 16


class TestScheduler(object):
    """TestScheduler. """
    def __init__(self, tests_list, num_jobs):
        """init method. """
        self.tests_list = tests_list
        self.num_jobs = num_jobs

        self.job_queue = Queue.Queue(0)
        self.exclusive_job_queue = Queue.Queue(0)

        self.run_result_lock = threading.Lock()
        # dict{key, {}}
        self.passed_run_results = {}
        self.failed_run_results = {}

        self.num_of_ran_tests = 0

    def _get_workers_num(self):
        """get the number of thread workers. """
        cpu_count = blade_util.cpu_count()
        max_workers = max(cpu_count, _MAX_WORKER_THREADS)
        if self.num_jobs <= 1:
            return 1
        elif self.num_jobs > max_workers:
            self.num_jobs = max_workers

        return min(len(self.tests_list), self.num_jobs)

    def _get_result(self, returncode):
        """translate result from returncode. """
        result = 'SUCCESS'
        if returncode != 0:
            result = _SIGNAL_MAP.get(returncode, 'FAILED')
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
        console.info('[%s/%s] Running %s' % (self.num_of_ran_tests, len(self.tests_list), cmd))
        p = subprocess.Popen(cmd,
                             env=test_env,
                             cwd=run_dir,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             close_fds=True,
                             shell=shell)
        job_thread.set_job_data(p, test_name, timeout)
        stdout = p.communicate()[0]
        result = self._get_result(p.returncode)
        msg = 'Output of %s:\n%s\n%s finished: %s\n' % (
                test_name, stdout, test_name, result)
        if console.verbosity_le('quiet') and p.returncode != 0:
            console.error(msg, prefix=False)
        else:
            console.info(msg)
            console.flush()

        return p.returncode

    def _run_job(self, job, job_thread):
        """run job, do not redirect the output. """
        target, run_dir, test_env, cmd = job
        test_name = target.fullname
        shell = target.data.get('run_in_shell', False)
        if shell:
            cmd = subprocess.list2cmdline(cmd)
        timeout = target.data.get('test_timeout')
        console.info('[%s/%s] Running %s' % (self.num_of_ran_tests, len(self.tests_list), cmd))
        p = subprocess.Popen(cmd, env=test_env, cwd=run_dir, close_fds=True, shell=shell)
        job_thread.set_job_data(p, test_name, timeout)
        p.wait()
        result = self._get_result(p.returncode)
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

        cost_time = time.time() - start_time

        run_result = TestRunResult(exit_code=returncode,
                start_time=start_time, cost_time=cost_time)

        with self.run_result_lock:
            if returncode == 0:
                self.passed_run_results[target.key] = run_result
            else:
                self.failed_run_results[target.key] = run_result
            self.num_of_ran_tests += 1

    def _join_thread(self, t):
        """Join thread and keep signal awareable"""
        # The Thread.join without timeout will block signals, which makes
        # blade can't be terminated by Ctrl-C
        while t.isAlive():
            t.join(1)

    def _wait_worker_threads(self, threads):
        """Wait for worker threads to complete. """
        test_timeout = config.get_item('global_config', 'test_timeout')
        try:
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
        except KeyboardInterrupt:
            console.debug('KeyboardInterrupt: Terminate workers...')
            for t in threads:
                t.terminate()
            raise

    def schedule_jobs(self):
        """scheduler. """
        if not self.tests_list:
            return

        num_of_workers = self._get_workers_num()
        console.info('spawn %d worker(s) to run tests' % num_of_workers)

        for i in self.tests_list:
            target = i[0]
            if target.data.get('exclusive'):
                self.exclusive_job_queue.put(i)
            else:
                self.job_queue.put(i)
        quiet = console.verbosity_le('quiet')
        redirect = num_of_workers > 1 or quiet
        threads = []
        for i in range(num_of_workers):
            t = WorkerThread(i, self.job_queue, self._process_job, redirect)
            t.start()
            threads.append(t)
        self._wait_worker_threads(threads)

        if not self.exclusive_job_queue.empty():
            console.info('spawn 1 worker to run exclusive tests')
            last_t = WorkerThread(num_of_workers, self.exclusive_job_queue,
                                  self._process_job, quiet)
            last_t.start()
            self._wait_worker_threads([last_t])

    def get_results(self):
        return self.passed_run_results, self.failed_run_results
