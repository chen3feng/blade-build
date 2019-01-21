# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Authors: Huan Yu <huanyu@tencent.com>
#          Feng Chen <phongchen@tencent.com>
#          Yi Wang <yiwang@tencent.com>
#          Chong Peng <michaelpeng@tencent.com>
# Date: October 20, 2011


"""
 This is the TestRunner module which executes the test programs.

"""


from collections import namedtuple
import os
import sys
import subprocess
import time

import binary_runner
import config
import console

from blade_util import md5sum
from test_scheduler import TestScheduler


_TEST_HISTORY_FILE = '.blade.test.stamp'
_TEST_EXPIRE_TIME = 86400  # 1 day
_REPORT_BANNER = '=' * 13


TestJob = namedtuple('TestJob', ['md5', 'reason'])
TestHistoryItem = namedtuple('TestHistoryItem', ['job', 'result'])


def _get_ignore_set():
    """ """
    ignore_env_vars = [
            # shell variables
            'PWD', 'OLDPWD', 'SHLVL', 'LC_ALL', 'TST_HACK_BASH_SESSION_ID',
            # CI variables
            'BUILD_DISPLAY_NAME',
            'BUILD_URL', 'BUILD_TAG', 'SVN_REVISION',
            'BUILD_ID', 'START_USER',
            'EXECUTOR_NUMBER', 'NODE_NAME', 'NODE_LABELS',
            'IF_PKG', 'BUILD_NUMBER', 'HUDSON_COOKIE',
            # ssh variables
            'SSH_CLIENT', 'SSH2_CLIENT',
            # vim variables
            'VIM', 'MYVIMRC', 'VIMRUNTIME']

    for i in range(30):
        ignore_env_vars.append('SVN_REVISION_%d' % i)

    return frozenset(ignore_env_vars)


env_ignore_set = _get_ignore_set()


def _diff_env(a, b):
    """Return difference of two environments dict"""
    seta = set([(k, a[k]) for k in a])
    setb = set([(k, b[k]) for k in b])
    return (dict(seta - setb), dict(setb - seta))


class TestRunner(binary_runner.BinaryRunner):
    """TestRunner. """
    def __init__(self, targets, options, target_database, direct_targets):
        """Init method. """
        # pylint: disable=too-many-locals, too-many-statements
        binary_runner.BinaryRunner.__init__(self, targets, options, target_database)
        self.direct_targets = direct_targets
        self.test_jobs = {}  # dict{key : TestJob}
        self.test_history = {}
        self.run_all_reason = ''
        self.skipped_tests = []
        self.coverage = getattr(options, 'coverage', False)
        if not self.options.fulltest:
            if os.path.exists(_TEST_HISTORY_FILE):
                try:
                    f = open(_TEST_HISTORY_FILE)
                    # pylint: disable=eval-used
                    self.test_history = eval(f.read())
                    f.close()
                except (IOError, SyntaxError):
                    console.warning('error loading incremental test history, will run full test')
                    self.run_all_reason = 'NO_HISTORY'

        if 'items' not in self.test_history:
            self.test_history['items'] = {}

        env_keys = os.environ.keys()
        env_keys = set(env_keys).difference(env_ignore_set)
        new_env = {key:os.environ[key] for key in env_keys}
        now = time.time()

        if not self.options.fulltest:
            if self.options.testargs != self.test_history.get('testargs', None):
                self.run_all_reason = 'ARGUMENT'
                console.info('all tests will run due to test arguments changed')

            old_env = self.test_history.get('env', {})
            if new_env != old_env:
                self.run_all_reason = 'ENVIRONMENT'
                console.info('all tests will run due to test environments changed:')
                (new, old) = _diff_env(new_env, old_env)
                if new:
                    console.info('new environments: %s' % new)
                if old:
                    console.info('old environments: %s' % old)

            last_time = int(round(self.test_history.get('last_time', 0)))
            interval = now - last_time

            if interval >= _TEST_EXPIRE_TIME or interval < 0:
                self.run_all_reason = 'STALE'
                console.info('all tests will run due to all passed tests are expired now')
        else:
            self.run_all_reason = 'FULLTEST'

        self.test_history['env'] = new_env
        self.test_history['last_time'] = now
        self.test_history['testargs'] = self.options.testargs

    def _get_test_target_md5sum(self, target):
        """Get test target md5sum. """
        # pylint: disable=too-many-locals
        related_file_list = []
        related_file_data_list = []
        test_file_name = os.path.abspath(self._executable(target))
        if os.path.exists(test_file_name):
            related_file_list.append(test_file_name)

        if target.data.get('dynamic_link'):
            for dep in self.targets[target.key].expanded_deps:
                dep_target = self.targets[dep]
                if 'cc_library' in dep_target.type:
                    lib_name = 'lib%s.so' % dep_target.name
                    lib_path = os.path.join(self.build_dir,
                                            dep_target.path,
                                            lib_name)
                    abs_lib_path = os.path.abspath(lib_path)
                    if os.path.exists(abs_lib_path):
                        related_file_list.append(abs_lib_path)

        for i in target.data['testdata']:
            if isinstance(i, tuple):
                data_target = i[0]
            else:
                data_target = i
            if '..' in data_target:
                continue
            if data_target.startswith('//'):
                data_target = data_target[2:]
                data_target_path = os.path.abspath(data_target)
            else:
                data_target_path = os.path.abspath('%s/%s' % (
                                                   target.path, data_target))
            if os.path.exists(data_target_path):
                related_file_data_list.append(data_target_path)

        related_file_list.sort()
        related_file_data_list.sort()

        test_target_str = ''
        test_target_data_str = ''
        for f in related_file_list:
            mtime = os.path.getmtime(f)
            ctime = os.path.getctime(f)
            test_target_str += str(mtime) + str(ctime)

        for f in related_file_data_list:
            mtime = os.path.getmtime(f)
            ctime = os.path.getctime(f)
            test_target_data_str += str(mtime) + str(ctime)

        return md5sum(test_target_str), md5sum(test_target_data_str)

    def _run_reason(self, target, md5sums):
        '''Return run reason for a given test'''
        if self.run_all_reason:
            return self.run_all_reason

        if target.data.get('always_run'):
            return 'ALWAYS_RUN'

        if target.key in self.direct_targets:
            return 'EXPLICIT'

        history = self.test_history['items'].get(target.fullname, None)
        if not history:
            return 'NO_HISTORY'

        if history.result.exit_code != 0:
            return 'LAST_FAILED'

        old_md5sum = history.job.md5
        if md5sums != old_md5sum:
            if isinstance(old_md5sum, tuple):
                if md5sums[0] != old_md5sum[0]:
                    return 'BINARY'
                else:
                    return 'TESTDATA'
            return 'STALE'
        return None

    def _collect_test_jobs(self):
        """Get incremental test run list. """
        for target in self.targets.values():
            if not target.type.endswith('_test'):
                continue
            new_md5sums = self._get_test_target_md5sum(target)
            reason = self._run_reason(target, new_md5sums)
            if reason:
                self.test_jobs[target.key] = TestJob(md5=new_md5sums, reason=reason)

    def _get_java_coverage_data(self):
        """
        Return a list of tuples(source directory, class directory, execution data)
        for each java_test.
            source directory: source directory of java_library target under test
            class directory: class directory of java_library target under test
            execution data: jacoco.exec collected by jacoco agent during testing
        """
        coverage_data = []
        for key in self.test_jobs:
            target = self.targets[key]
            if target.type != 'java_test':
                continue
            execution_data = os.path.join(self._runfiles_dir(target), 'jacoco.exec')
            if not os.path.isfile(execution_data):
                continue
            target_under_test = target.data.get('target_under_test')
            if not target_under_test:
                continue
            target_under_test = self.target_database[target_under_test]
            source_dir = target_under_test._get_sources_dir()
            class_dir = target_under_test._get_classes_dir()
            coverage_data.append((source_dir, class_dir, execution_data))

        return coverage_data

    def _generate_java_coverage_report(self):
        java_test_config = config.get_section('java_test_config')
        jacoco_home = java_test_config['jacoco_home']
        coverage_reporter = java_test_config['coverage_reporter']
        if not jacoco_home or not coverage_reporter:
            console.warning('Missing jacoco home or coverage report generator '
                            'in global configuration. '
                            'Abort java coverage report generation.')
            return
        jacoco_libs = os.path.join(jacoco_home, 'lib', 'jacocoant.jar')
        report_dir = os.path.join(self.build_dir, 'java', 'coverage_report')
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        coverage_data = self._get_java_coverage_data()
        if coverage_data:
            cmd = ['java -classpath %s:%s com.tencent.gdt.blade.ReportGenerator' % (
                coverage_reporter, jacoco_libs)]
            cmd.append(report_dir)
            for data in coverage_data:
                cmd.append(','.join(data))
            cmd_str = ' '.join(cmd)
            console.info('Generating java coverage report')
            console.info(cmd_str)
            if subprocess.call(cmd_str, shell=True):
                console.warning('Failed to generate java coverage report')

    def _generate_coverage_report(self):
        self._generate_java_coverage_report()

    def _merge_run_results_to_history(self, run_results):
        for key, run_result in run_results.items():
            self.test_history['items'][self.targets[key].fullname] = \
                TestHistoryItem(self.test_jobs[key], run_result)

    def _update_test_history(self, scheduler):
        """update test history and save it to file. """
        self._merge_run_results_to_history(scheduler.passed_run_results)
        self._merge_run_results_to_history(scheduler.failed_run_results)
        with open(_TEST_HISTORY_FILE, 'w') as f:
            print >> f, str(self.test_history)

    def _show_skipped_tests_detail(self):
        """Show tests skipped. """
        self.skipped_tests.sort()
        for key in self.skipped_tests:
            console.info('%s skipped' % key, prefix=False)

    def _show_tests_detail(self, scheduler):
        """Show the tests detail after scheduling them. """
        tests = []
        for key, result in scheduler.passed_run_results.iteritems():
            reason = self.test_jobs[key].reason
            tests.append((key, result.cost_time, reason, result.exit_code))
        tests.sort(key=lambda x: x[1])

        console.info('{0} Testing Detail {0}'.format(_REPORT_BANNER))
        self._show_skipped_tests_detail()
        for key, costtime, reason, result in tests:
            console.info('%s:%s triggered by %s, exit(%s), cost %.2f s' % (
                         key[0], key[1], reason, result, costtime), prefix=False)

    def _show_skipped_tests_summary(self):
        """show tests skipped summary. """
        if self.skipped_tests:
            console.info('%d tests skipped when doing incremental test.' %
                         len(self.skipped_tests))
            console.info('Specify --full-test to run all tests.')

    def _show_tests_summary(self, scheduler):
        """Show tests summary. """
        run_tests = len(scheduler.passed_run_results) + len(scheduler.failed_run_results)
        console.info('{0} Testing Summary {0}'.format(_REPORT_BANNER))
        self._show_skipped_tests_summary()

        console.info('Run %d tests' % run_tests)
        failed_run_results = scheduler.failed_run_results
        if failed_run_results:
            console.error('%d tests failed:' % len(failed_run_results))
            for target_key, result in failed_run_results:
                print target_key
                target = self.targets[target_key]
                print >>sys.stderr, '%s, exit code: %s' % (
                        target.fullname, result.exit_code)
            console.info('%d tests passed.' % (run_tests - len(failed_run_results)))
        else:
            console.info('All tests passed!')

    def _show_tests_result(self, scheduler):
        """Show test detail and summary according to the options. """
        if self.options.show_details:
            self._show_tests_detail(scheduler)
        self._show_tests_summary(scheduler)

    def run(self):
        """Run all the test target programs. """
        self._collect_test_jobs()
        tests_run_list = []
        for target_key in self.test_jobs:
            target = self.target_database[target_key]
            test_env = self._prepare_env(target)
            cmd = [os.path.abspath(self._executable(target))]
            cmd += self.options.args
            if console.color_enabled:
                test_env['GTEST_COLOR'] = 'yes'
            else:
                test_env['GTEST_COLOR'] = 'no'
            test_env['GTEST_OUTPUT'] = 'xml'
            test_env['HEAPCHECK'] = target.data.get('heap_check', '')
            pprof_path = config.get_item('cc_test_config', 'pprof_path')
            if pprof_path:
                test_env['PPROF_PATH'] = os.path.abspath(pprof_path)
            if self.coverage:
                test_env['BLADE_COVERAGE'] = 'true'
            tests_run_list.append((target, self._runfiles_dir(target), test_env, cmd))

        sys.stdout.flush()
        scheduler = TestScheduler(tests_run_list, self.options.test_jobs)
        try:
            scheduler.schedule_jobs()
        except KeyboardInterrupt:
            console.warning('KeyboardInterrupt, all tests stopped')
            console.flush()

        if self.coverage:
            self._generate_coverage_report()

        self._clean_env()
        self._update_test_history(scheduler)
        self._show_tests_result(scheduler)
        return 0 if len(scheduler.passed_run_results) == len(self.test_jobs) else 1
