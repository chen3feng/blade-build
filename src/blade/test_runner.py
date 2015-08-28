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


import os
import sys
import time

import binary_runner
import configparse
import console

from blade_util import environ_add_path
from blade_util import md5sum
from test_scheduler import TestScheduler


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
        binary_runner.BinaryRunner.__init__(self, targets, options, target_database)
        self.direct_targets = direct_targets
        self.inctest_md5_file = '.blade.test.stamp'
        self.tests_detail_file = './blade_tests_detail'
        self.inctest_run_list = []
        self.last_test_stamp = {}
        self.last_test_stamp['md5'] = {}
        self.test_stamp = {}
        self.test_stamp['md5'] = {}
        self.valid_inctest_time_interval = 86400
        self.tests_run_map = {}
        self.run_all_reason = ''
        self.title_str = '=' * 13
        self.skipped_tests = []
        if not self.options.fulltest:
            if os.path.exists(self.inctest_md5_file):
                try:
                    self.last_test_stamp = eval(open(self.inctest_md5_file).read())
                except (IOError, SyntaxError):
                    console.warning('error loading incremental test history, will run full test')
                    self.run_all_reason = 'NO_HISTORY'

        self.test_stamp['testarg'] = md5sum(str(self.options.args))
        env_keys = os.environ.keys()
        env_keys = list(set(env_keys).difference(env_ignore_set))
        env_keys.sort()
        last_test_stamp = {}
        for env_key in env_keys:
            last_test_stamp[env_key] = os.environ[env_key]
        self.test_stamp['env'] = last_test_stamp
        self.test_stamp['inctest_time'] = time.time()

        if not self.options.fulltest:
            if self.test_stamp['testarg'] != (
                    self.last_test_stamp.get('testarg', None)):
                self.run_all_reason = 'ARGUMENT'
                console.info('all tests will run due to test arguments changed')

            new_env = self.test_stamp['env']
            old_env = self.last_test_stamp.get('env', {})
            if isinstance(old_env, str):  # For old test record
                old_env = {}
            if new_env != old_env:
                self.run_all_reason = 'ENVIRONMENT'
                console.info('all tests will run due to test environments changed:')
                (new, old) = _diff_env(new_env, old_env)
                if new:
                    console.info('new environments: %s' % new)
                if old:
                    console.info('old environments: %s' % old)

            this_time = int(round(self.test_stamp['inctest_time']))
            last_time = int(round(self.last_test_stamp.get('inctest_time', 0)))
            interval = this_time - last_time

            if interval >= self.valid_inctest_time_interval or interval < 0:
                self.run_all_reason = 'STALE'
                console.info('all tests will run due to all passed tests are invalid now')
        else:
            self.run_all_reason = 'FULLTEST'

    def _get_test_target_md5sum(self, target):
        """Get test target md5sum. """
        related_file_list = []
        related_file_data_list = []
        test_file_name = os.path.abspath(self._executable(target))
        if os.path.exists(test_file_name):
            related_file_list.append(test_file_name)

        if target.data['dynamic_link']:
            target_key = (target.path, target.name)
            for dep in self.target_database[target_key].expanded_deps:
                dep_target = self.target_database[dep]
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

    def _generate_inctest_run_list(self):
        """Get incremental test run list. """
        for target in self.targets.values():
            if target.type != 'cc_test':
                continue
            target_key = (target.path, target.name)
            test_file_name = os.path.abspath(self._executable(target))
            self.test_stamp['md5'][test_file_name] = self._get_test_target_md5sum(target)
            if self.run_all_reason:
                self.tests_run_map[target_key] = {
                        'runfile': test_file_name,
                        'result': '',
                        'reason': self.run_all_reason,
                        'costtime': 0}
                continue

            if target_key in self.direct_targets:
                self.inctest_run_list.append(target)
                self.tests_run_map[target_key] = {
                        'runfile': test_file_name,
                        'result': '',
                        'reason': 'EXPLICIT',
                        'costtime': 0}
                continue

            old_md5sum = self.last_test_stamp['md5'].get(test_file_name, None)
            new_md5sum = self.test_stamp['md5'][test_file_name]
            if new_md5sum != old_md5sum:
                self.inctest_run_list.append(target)
                reason = ''
                if isinstance(old_md5sum, tuple):
                    if old_md5sum == (0, 0):
                        reason = 'LAST_FAILED'
                    else:
                        if new_md5sum[0] != old_md5sum[0]:
                            reason = 'BINARY'
                        else:
                            reason = 'TESTDATA'
                else:
                    reason = 'STALE'
                self.tests_run_map[target_key] = {
                        'runfile': test_file_name,
                        'result': '',
                        'reason': reason,
                        'costtime': 0}

        # Append old md5sum that not existed into new
        old_keys = set(self.last_test_stamp['md5'].keys())
        new_keys = set(self.test_stamp['md5'].keys())
        diff_keys = old_keys.difference(new_keys)
        for key in list(diff_keys):
            self.test_stamp['md5'][key] = self.last_test_stamp['md5'][key]

    def _check_inctest_md5sum_file(self):
        """check the md5sum file size, remove it when it is too large.
           It is 2G by default.
        """
        if os.path.exists(self.inctest_md5_file):
            if os.path.getsize(self.inctest_md5_file) > 2 * 1024 * 1024 * 1024:
                console.warning('Will remove the md5sum file for incremental '
                                'test for it is oversized')
                os.remove(self.inctest_md5_file)

    def _write_test_history(self):
        """write md5sum to file. """
        f = open(self.inctest_md5_file, 'w')
        print >> f, str(self.test_stamp)
        f.close()
        self._check_inctest_md5sum_file()

    def _write_tests_detail_map(self):
        """write the tests detail map for further use. """
        f = open(self.tests_detail_file, 'w')
        print >> f, str(self.tests_run_map)
        f.close()

    def _show_tests_detail(self):
        """show the tests detail after scheduling them. """
        sort_buf = []
        for key in self.tests_run_map:
            costtime = self.tests_run_map.get(key, {}).get('costtime', 0)
            sort_buf.append((key, costtime))
        sort_buf.sort(key=lambda x: x[1])

        if self.tests_run_map:
            console.info('%s Testing detail %s' % (self.title_str, self.title_str))
        for key, costtime in sort_buf:
            reason = self.tests_run_map.get(key, {}).get('reason', 'UNKNOWN')
            result = self.tests_run_map.get(key, {}).get('result',
                                                         'INTERRUPTED')
            if 'SIG' in result:
                result = 'with %s' % result
            console.info('%s:%s triggered by %s, exit(%s), cost %.2f s' % (
                         key[0], key[1], reason, result, costtime), prefix=False)

    def _finish_tests(self):
        """finish some work before return from runner. """
        self._write_test_history()
        if self.options.show_details:
            self._write_tests_detail_map()
            if not self.run_all_reason:
                self._show_skipped_tests_detail()
                self._show_skipped_tests_summary()
            self._show_tests_detail()
        elif not self.run_all_reason:
            self._show_skipped_tests_summary()

    def _show_skipped_tests_detail(self):
        """show tests skipped. """
        if not self.skipped_tests:
            return
        self.skipped_tests.sort()
        console.info('skipped tests')
        for target_key in self.skipped_tests:
            print '%s:%s' % (target_key[0], target_key[1])

    def _show_skipped_tests_summary(self):
        """show tests skipped summary. """
        console.info('%d tests skipped when doing incremental test' % len(self.skipped_tests))
        console.info('to run all tests, please specify --full-test argument')

    def run(self):
        """Run all the cc_test target programs. """
        failed_targets = []
        self._generate_inctest_run_list()
        tests_run_list = []
        for target in self.targets.values():
            if target.type != 'cc_test':
                continue
            if (not self.run_all_reason) and target not in self.inctest_run_list:
                if not target.data.get('always_run'):
                    self.skipped_tests.append((target.path, target.name))
                    continue
            test_env = self._prepare_env(target)
            cmd = [os.path.abspath(self._executable(target))]
            cmd += self.options.args

            sys.stdout.flush()  # make sure output before scons if redirected

            if console.color_enabled:
                test_env['GTEST_COLOR'] = 'yes'
            else:
                test_env['GTEST_COLOR'] = 'no'
            test_env['GTEST_OUTPUT'] = 'xml'
            test_env['HEAPCHECK'] = target.data.get('heap_check', '')
            config = configparse.blade_config.get_config('cc_test_config')
            pprof_path = config['pprof_path']
            if pprof_path:
                test_env['PPROF_PATH'] = os.path.abspath(pprof_path)
            tests_run_list.append((target,
                                   self._runfiles_dir(target),
                                   test_env,
                                   cmd))
        concurrent_jobs = 0
        concurrent_jobs = self.options.test_jobs
        scheduler = TestScheduler(tests_run_list,
                                  concurrent_jobs,
                                  self.tests_run_map)
        scheduler.schedule_jobs()

        self._clean_env()
        console.info('%s Testing Summary %s' % (self.title_str, self.title_str))
        console.info('Run %d test targets' % scheduler.num_of_run_tests)

        failed_targets = scheduler.failed_targets
        if failed_targets:
            console.error('%d tests failed:' % len(failed_targets))
            for target in failed_targets:
                print '%s:%s, exit code: %s' % (
                    target.path, target.name, target.data['test_exit_code'])
                test_file_name = os.path.abspath(self._executable(target))
                # Do not skip failed test by default
                if test_file_name in self.test_stamp['md5']:
                    self.test_stamp['md5'][test_file_name] = (0, 0)
            console.info('%d tests passed' % (
                scheduler.num_of_run_tests - len(failed_targets)))
            self._finish_tests()
            return 1
        else:
            console.info('All tests passed!')
            self._finish_tests()
            return 0
