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

from __future__ import absolute_import
from __future__ import print_function

import os
import re
import subprocess
import time
from collections import namedtuple

from blade import binary_runner
from blade import config
from blade import console
from blade.blade_util import md5sum, iteritems
from blade.test_scheduler import TestScheduler
# pylint: disable=unused-import
from blade.test_scheduler import TestRunResult  # Used by eval

# Used by eval when loading test history
_TEST_HISTORY_FILE = '.blade.test.stamp'
_TEST_EXPIRE_TIME = 86400  # 1 day


TestJob = namedtuple('TestJob',
        ['reason', 'binary_md5', 'testdata_md5', 'env_md5', 'args'])
TestHistoryItem = namedtuple('TestHistoryItem', ['job', 'result'])


def _filter_out_ignored_envs(names):
    """Filter out any names which matches `global_config.test_ignored_envs`"""
    ignored_names = config.get_item('global_config', 'test_ignored_envs')
    if not ignored_names:
        return names
    rx = '(' + '|'.join(['(%s)' % name for name in ignored_names]) + ')$'
    names_rx = re.compile(rx)
    return set(name for name in names if not names_rx.match(name) )


def _diff_env(a, b):
    """Return difference of two environments dict"""
    seta = set([(k, a[k]) for k in a])
    setb = set([(k, b[k]) for k in b])
    return dict(seta - setb), dict(setb - seta)


class TestRunner(binary_runner.BinaryRunner):
    """Run specified tests and collect the results"""
    def __init__(self, targets, options, target_database, direct_targets, skip_tests):
        """Init method. """
        # pylint: disable=too-many-locals, too-many-statements
        binary_runner.BinaryRunner.__init__(self, targets, options, target_database)
        self.direct_targets = direct_targets

        # Test jobs should be run
        self.test_jobs = {}  # dict{key : TestJob}

        self.skip_tests = skip_tests  # Tests to be skipped
        self.skipped_tests = []

        # Test history is the key to implement incremental test.
        # It will be loaded from file before test, compared with test jobs,
        # and be updated and saved to file back after test.
        self.test_history_file = os.path.join(self.build_dir, _TEST_HISTORY_FILE)
        self.test_history = {}  # {key, dict{}}

        self._load_test_history()
        self._update_test_history()

    def _load_test_history(self):
        if os.path.exists(self.test_history_file):
            with open(self.test_history_file) as f:
                try:
                    # pylint: disable=eval-used
                    self.test_history = eval(f.read())
                except (SyntaxError, NameError, TypeError) as e:
                    console.debug('Exception when loading test history: %s' % e)
                    console.warning('error loading incremental test history, will run full test')

        if 'items' not in self.test_history:
            self.test_history['items'] = {}

    def _update_test_history(self):
        old_env = self.test_history.get('env', {})
        env_keys = _filter_out_ignored_envs(os.environ.keys())
        new_env = dict((key, os.environ[key]) for key in env_keys)
        if old_env and new_env != old_env:
            console.notice('Some tests will be run due to test environments changed:')
            new, old = _diff_env(new_env, old_env)
            if new:
                console.notice('new environments: %s' % new)
            if old:
                console.notice('old environments: %s' % old)

        self.test_history['env'] = new_env
        self.env_md5 = md5sum(str(sorted(iteritems(new_env))))

    def _save_test_history(self, passed_run_results, failed_run_results):
        """update test history and save it to file. """
        self._merge_run_results_to_history(passed_run_results)
        self._merge_run_results_to_history(failed_run_results)
        with open(self.test_history_file, 'w') as f:
            print(str(self.test_history), file=f)

    def _merge_run_results_to_history(self, run_results):
        for key, run_result in iteritems(run_results):
            self.test_history['items'][key] = TestHistoryItem(self.test_jobs[key], run_result)

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

        test_target = []
        test_target_data = []
        for f in related_file_list:
            test_target.append(str(os.path.getmtime(f)))
            test_target.append(str(os.path.getctime(f)))

        for f in related_file_data_list:
            test_target_data.append(str(os.path.getmtime(f)))
            test_target_data.append(str(os.path.getctime(f)))
        return md5sum(''.join(test_target)), md5sum(''.join(test_target_data))

    def _skip_test(self, target):
        """Whether skip this test"""
        if not self.skip_tests:
            return False
        for skip_test in self.skip_tests:
            if skip_test == target.fullname:
                return True
            skip_test = skip_test.split(':')
            if skip_test[1] == '*' and skip_test[0] == target.path:
                return True
            if (skip_test[1] == '...' and (target.path == skip_test[0] or
                                           target.path.startswith(skip_test[0] + os.path.sep))):
                return True
        return False

    def _run_reason(self, target, binary_md5, testdata_md5):
        """Return run reason for a given test"""

        if self._skip_test(target):
            console.info('//%s is skipped by --skip-test' % target.fullname)
            return None

        if self.options.full_test:
            return 'FULL_TEST'

        if target.data.get('always_run'):
            return 'ALWAYS_RUN'
        if target.key in self.direct_targets:
            return 'EXPLICIT'

        history = self.test_history['items'].get(target.key)
        if not history:
            return 'NO_HISTORY'

        if history.result.exit_code != 0:
            return 'LAST_FAILED'

        last_time = history.result.start_time
        interval = time.time() - last_time
        if interval >= _TEST_EXPIRE_TIME or interval < 0:
            return 'STALE'

        if history.job.binary_md5 != binary_md5:
            return 'BINARY'
        if history.job.testdata_md5 != testdata_md5:
            return 'TESTDATA'
        if history.job.env_md5 != self.env_md5:
            return 'ENVIRONMENT'
        if history.job.args != self.options.args:
            return 'ARGUMENT'

        return None

    def _collect_test_jobs(self):
        """Get incremental test run list. """
        for target in self.targets.values():
            if not target.type.endswith('_test'):
                continue
            binary_md5, testdata_md5 = self._get_test_target_md5sum(target)
            reason = self._run_reason(target, binary_md5, testdata_md5)
            if reason:
                self.test_jobs[target.key] = TestJob(
                        reason=reason,
                        binary_md5=binary_md5,
                        testdata_md5=testdata_md5,
                        env_md5=self.env_md5,
                        args=self.options.args)
            else:
                self.skipped_tests.append(target.key)

    def _get_jacoco_coverage_data(self):
        """Return a tuples of execution data files, classes directories, source directories.
        for each java_test.
            execution data: jacoco.exec collected by jacoco agent during testing
            class directory: class directory of target under test
            source directory: source directory of target under test
        """
        execfiles = []
        source_dirs = []
        classes_dirs = []
        for key in self.test_jobs:
            target = self.targets[key]

            execution_data = os.path.join(self._runfiles_dir(target), 'jacoco.exec')
            if not os.path.isfile(execution_data):
                continue
            execfiles.append(execution_data)

            for dkey in target.deps:
                dep = self.target_database[dkey]
                if not dep.data.get('jacoco_coverage'):
                    continue
                classes_dir = dep._get_classes_dir()
                if not os.path.exists(classes_dir):
                    classes_dir = dep._get_target_file('jar')
                classes_dirs.append(classes_dir)

                source_dir = dep._get_sources_dir()
                source_dirs.append(source_dir)

        return execfiles, classes_dirs, source_dirs

    def _generate_jacoco_coverage_report(self):
        """Run jacococli to generate coverage report"""
        # TODO(chen3feng): Support generating other formats
        java_test_config = config.get_section('java_test_config')
        jacoco_home = java_test_config['jacoco_home']
        if not jacoco_home:
            console.warning('Missing jacoco home in java_test configuration. '
                            'Abort java coverage report generation.')
            return
        report_dir = os.path.join(self.build_dir, 'jacoco_coverage_report')
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)

        execfiles, classes_dirs, source_dirs = self._get_jacoco_coverage_data()
        if execfiles:
            java = 'java'
            java_home = config.get_item('java_config', 'java_home')
            if java_home:
                java = os.path.join(java_home, 'bin', 'java')
            jacococli = os.path.join(jacoco_home, 'lib', 'jacococli.jar')
            classfiles = ['--classfiles ' + files for files in classes_dirs]
            sourcefiles = ['--sourcefiles ' + files for files in source_dirs]
            # See https://www.jacoco.org/jacoco/trunk/doc/cli.html
            cmd_str = ('{java} -jar {jacococli} report {execfiles} {classfiles} {sourcefiles} '
                       '--html {report_dir}').format(
                              java=java, jacococli=jacococli, execfiles=' '.join(execfiles),
                              classfiles=' '.join(classfiles), sourcefiles=' '.join(sourcefiles),
                              report_dir=report_dir)
            console.info('Generating java coverage report `%s`' % report_dir)
            console.debug(cmd_str)
            if subprocess.call(cmd_str, shell=True) != 0:
                console.warning('Failed to generate java coverage report')

    def _generate_coverage_report(self):
        self._generate_jacoco_coverage_report()

    def _show_banner(self, text):
        pads = int((76 - len(text)) / 2)
        console.notice('{0} {1} {0}'.format('=' * pads, text), prefix=False)

    def _show_skipped_tests(self):
        """Show tests skipped. """
        if self.skipped_tests:
            console.info('%d skipped tests:' % len(self.skipped_tests))
            self.skipped_tests.sort()
            for key in self.skipped_tests:
                console.info('//%s:%s' % key, prefix=False)

    def _show_run_results(self, run_results, is_error=False):
        """Show the tests detail after scheduling them. """
        tests = []
        for key, result in iteritems(run_results):
            reason = self.test_jobs[key].reason
            tests.append((key, result.cost_time, reason, result.exit_code))
        tests.sort(key=lambda x: x[1])
        output_function = console.error if is_error else console.info
        for key, costtime, reason, result in tests:
            output_function('%s:%s triggered by %s, exit(%s), cost %.2f s' % (
                            key[0], key[1], reason, result, costtime), prefix=False)

    def _collect_slow_tests(self, run_results):
        return [(result.cost_time, key) for key, result in iteritems(run_results)
                if result.cost_time > self.options.show_tests_slower_than]

    def _show_slow_tests(self, passed_run_results, failed_run_results):
        slow_tests = (self._collect_slow_tests(passed_run_results) +
                      self._collect_slow_tests(failed_run_results))
        if slow_tests:
            console.warning('%d slow tests:' % len(slow_tests))
            for cost_time, key in sorted(slow_tests):
                console.warning('%.4gs\t//%s:%s' % (cost_time, key[0], key[1]), prefix=False)

    def _show_tests_summary(self, passed_run_results, failed_run_results):
        """Show tests summary. """
        self._show_banner('Testing Summary')
        console.info('%d tests scheduled to run by scheduler.' % (len(self.test_jobs)))
        if self.skipped_tests:
            console.info('%d tests skipped when doing incremental test.' %
                         len(self.skipped_tests))
            console.info('You can specify --full-test to run all tests.')

        run_tests = len(passed_run_results) + len(failed_run_results)

        if len(passed_run_results) == len(self.test_jobs):
            console.notice('All %d tests passed!' % len(passed_run_results))
            return

        msg = ['total %d tests' % len(self.test_jobs)]
        if passed_run_results:
            msg.append('%d passed' % len(passed_run_results))
        if failed_run_results:
            msg.append('%d failed' % len(failed_run_results))
        cancelled_tests = len(self.test_jobs) - run_tests
        if cancelled_tests:
            msg.append('%d cancelled' % cancelled_tests)
        console.error(', '.join(msg) + '.')

    def _show_tests_result(self, passed_run_results, failed_run_results):
        """Show test details and summary according to the options. """
        if self.options.show_details:
            self._show_banner('Testing Details')
            self._show_skipped_tests()
            if passed_run_results:
                console.info('passed tests:')
                self._show_run_results(passed_run_results)
        if self.options.show_tests_slower_than is not None:
            self._show_slow_tests(passed_run_results, failed_run_results)
        if failed_run_results:  # Always show details of failed tests
            console.error('failed tests:')
            self._show_run_results(failed_run_results, is_error=True)
        self._show_tests_summary(passed_run_results, failed_run_results)

    def run(self):
        """Run all the test target programs. """
        self._collect_test_jobs()
        tests_run_list = []
        for target_key in self.test_jobs:
            target = self.target_database[target_key]
            test_env = self._prepare_env(target)
            cmd = [os.path.abspath(self._executable(target))]
            cmd += self.options.args
            if console.color_enabled():
                test_env['GTEST_COLOR'] = 'yes'
            else:
                test_env['GTEST_COLOR'] = 'no'
            test_env['GTEST_OUTPUT'] = 'xml'
            test_env['HEAPCHECK'] = target.data.get('heap_check', '')
            pprof_path = config.get_item('cc_test_config', 'pprof_path')
            if pprof_path:
                test_env['PPROF_PATH'] = os.path.abspath(pprof_path)
            if self.options.coverage:
                test_env['BLADE_COVERAGE'] = 'true'
            tests_run_list.append((target, self._runfiles_dir(target), test_env, cmd))

        console.notice('%d tests to run' % len(tests_run_list))
        console.flush()
        scheduler = TestScheduler(tests_run_list, self.options.test_jobs)
        try:
            scheduler.schedule_jobs()
        except KeyboardInterrupt:
            console.clear_progress_bar()
            console.error('KeyboardInterrupt, all tests stopped')
            console.flush()

        if self.options.coverage:
            self._generate_coverage_report()

        self._clean_env()

        passed_run_results, failed_run_results = scheduler.get_results()
        self._save_test_history(passed_run_results, failed_run_results)
        self._show_tests_result(passed_run_results, failed_run_results)

        return 0 if len(passed_run_results) == len(self.test_jobs) else 1
