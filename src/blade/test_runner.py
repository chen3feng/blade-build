"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Authors: Huan Yu <huanyu@tencent.com>
          Feng Chen <phongchen@tencent.com>
          Yi Wang <yiwang@tencent.com>
          Chong Peng <michaelpeng@tencent.com>
 Date: October 20, 2011

 This is the TestRunner module which executes the test programs.

"""


import os
import shutil
import subprocess
import sys
import time
import blade_util
from blade_util import error_exit
from blade_util import get_cwd
from blade_util import info
from blade_util import info_str
from blade_util import md5sum
from blade_util import warning
from test_scheduler import TestScheduler


def _get_ignore_set():
    """ """
    ignore_env_vars = [
            # shell variables
            'PWD', 'OLDPWD', 'SHLVL', 'LC_ALL', 'TST_HACK_BASH_SESSION_ID',
            # CI variables
            'BUILD_URL', 'BUILD_TAG', 'SVN_REVISION',
            'BUILD_ID', 'EXECUTOR_NUMBER', 'START_USER',
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


class TestRunner(object):
    """TestRunner. """
    def __init__(self, targets, options, prebuilt_file_map={}, target_database={}):
        """Init method. """
        self.targets = targets
        self.build_dir = "build%s_%s" % (options.m, options.profile)
        self.options = options
        self.run_list = ['cc_binary',
                         'dynamic_cc_binary',
                         'cc_test',
                         'dynamic_cc_test']
        self.prebuilt_file_map = prebuilt_file_map
        self.target_database = target_database

        self.inctest_md5_file = ".blade.test.stamp"
        self.tests_detail_file = "./blade_tests_detail"
        self.run_all = False
        self.inctest_run_list = []
        self.testarg_dict = {}
        self.env_dict = {}
        self.cur_testarg_dict = {}
        self.cur_env_dict = {}
        self.inctest_md5_buffer = []
        self.target_dict = {}
        self.cur_target_dict = {}
        self.option_has_fulltest = False
        self.valid_inctest_time_interval = 86400
        self.last_inctest_time_dict = {}
        self.this_inctest_time_dict = {}
        self.tests_run_map = {}
        self.run_all_reason = ''
        self.title_str = '='*13
        self.skipped_tests = []
        if hasattr(self.options, 'fulltest'):
            self.option_has_fulltest = True
        if self.option_has_fulltest and (not self.options.fulltest):
            if os.path.exists(self.inctest_md5_file):
                for line in open(self.inctest_md5_file):
                    self.inctest_md5_buffer.append(line[:-1])
            buf_len = len(self.inctest_md5_buffer)
            if buf_len < 2 and buf_len > 0 :
                if os.path.exists(self.inctest_md5_file):
                    os.remove(self.inctest_md5_file)
                error_exit("bad incremental test md5 file, removed")
            if self.inctest_md5_buffer:
                self.testarg_dict = eval(self.inctest_md5_buffer[0])
                self.env_dict = eval(self.inctest_md5_buffer[1])
            if buf_len >= 3:
                self.target_dict = eval(self.inctest_md5_buffer[2])
            if buf_len >= 4:
                self.last_inctest_time_dict = eval(self.inctest_md5_buffer[3])
        if hasattr(self.options, 'testargs'):
            self.cur_testarg_dict['testarg'] = md5sum(self.options.testargs)
        else:
            self.cur_testarg_dict['testarg'] = None
        env_keys = os.environ.keys()
        env_keys = list(set(env_keys).difference(env_ignore_set))
        env_keys.sort()
        env_dict = {}
        for env_key in env_keys:
            env_dict[env_key] = os.environ[env_key]
        self.cur_env_dict['env'] = env_dict
        self.this_inctest_time_dict['inctest_time'] = time.time()

        if self.option_has_fulltest and (not self.options.fulltest):
            if self.cur_testarg_dict['testarg'] != (
                    self.testarg_dict.get('testarg', None)):
                self.run_all = True
                self.run_all_reason = 'ARGUMENT'
                info("all tests will run due to test arguments changed")

            new_env = self.cur_env_dict['env']
            old_env = self.env_dict.get('env', {})
            if isinstance(old_env, str): # For old test record
                old_env = {}
            if new_env != old_env:
                self.run_all = True
                self.run_all_reason = 'ENVIRONMENT'
                (new, old) = _diff_env(new_env, old_env)
                info("all tests will run due to test environments changed:")
                if new:
                    info("new environments: %s" % new)
                if old:
                    info("old environments: %s" % old)

            this_time = int(round(self.this_inctest_time_dict['inctest_time']))
            last_time = int(round(self.last_inctest_time_dict.get('inctest_time', 0)))
            interval = this_time - last_time

            if interval >= self.valid_inctest_time_interval or interval < 0:
                self.run_all = True
                self.run_all_reason = 'STALE'
                info("all tests will run due to all passed tests are invalid now")
        if self.option_has_fulltest and self.options.fulltest:
            self.run_all = True
            self.run_all_reason = 'FULLTEST'

    def _test_executable(self, target):
        """Returns the executable path. """
        return "%s/%s/%s" % (self.build_dir, target['path'], target['name'])

    def _runfiles_dir(self, target):
        """Returns runfiles dir. """
        return "./%s.runfiles" % (self._test_executable(target))

    def _prepare_run_env(self, target):
        """Prepare the run environment. """
        profile_link_name = os.path.basename(self.build_dir)
        target_dir = os.path.dirname(self._test_executable(target))
        lib_link = os.path.join(target_dir, profile_link_name)
        if os.path.exists(lib_link):
            os.remove(lib_link)
        os.symlink(os.path.abspath(self.build_dir), lib_link)

    def _get_prebuilt_files(self, target):
        """Get prebuilt files for one target that it depends. """
        file_list = []
        target_key = (target['path'], target['name'])
        for dep in self.target_database.get(target_key, {}).get('deps', []):
            target_type = self.target_database.get(dep, {}).get('type', '')
            if target_type == 'prebuilt_cc_library':
                prebuilt_file = self.prebuilt_file_map.get(dep, None)
                if prebuilt_file:
                    file_list.append(prebuilt_file)
        return file_list

    def __check_link_name(self, link_name, link_name_list):
        """check the link name is valid or not. """
        link_name_norm = os.path.normpath(link_name)
        if link_name in link_name_list:
            return "AMBIGUOUS", None
        long_path = ''
        short_path = ''
        short_len = 0
        for item in link_name_list:
            item_norm = os.path.normpath(item)
            if len(link_name_norm) >= len(item_norm):
                (long_path, short_path) = (link_name_norm, item_norm)
            else:
                (long_path, short_path) = (item_norm, link_name_norm)
            if long_path.startswith(short_path) and (
                    long_path[len(short_path)] == '/'):
                return "INCOMPATIBLE", item
        else:
            return  "VALID", None

    def _prepare_test_env(self, target):
        """Prepare the test environment. """
        shutil.rmtree(self._runfiles_dir(target), ignore_errors=True)
        os.mkdir(self._runfiles_dir(target))
        # add build profile symlink
        profile_link_name = os.path.basename(self.build_dir)
        os.symlink(os.path.abspath(self.build_dir),
                   os.path.join(self._runfiles_dir(target), profile_link_name))

        # add pre build library symlink
        for prebuilt_file in self._get_prebuilt_files(target):
            os.symlink(os.path.abspath(prebuilt_file[0]),
                       os.path.join(self._runfiles_dir(target), prebuilt_file[1]))

        link_name_list = []
        for i in target['options']['testdata']:
            if isinstance(i, tuple):
                data_target = i[0]
                link_name = i[1]
            else:
                data_target = link_name = i
            if '..' in data_target:
                continue
            if link_name.startswith('//'):
                link_name = link_name[2:]
            err_msg, item = self.__check_link_name(link_name, link_name_list)
            if err_msg == "AMBIGUOUS":
                error_exit("Ambiguous testdata of //%s:%s: %s, exit..." % (
                             target['path'], target['name'], link_name))
            elif err_msg == "INCOMPATIBLE":
                error_exit("%s could not exist with %s in testdata of //%s:%s" % (
                           link_name, item, target['path'], target['name']))
            link_name_list.append(link_name)
            try:
                os.makedirs(os.path.dirname('%s/%s' % (
                        self._runfiles_dir(target), link_name)))
            except os.error:
                pass
            if os.path.exists(os.path.abspath('%s/%s' % (
                              self._runfiles_dir(target), link_name))):
                error_exit("%s already existed, could not prepare testdata for "
                           "//%s:%s" % (link_name, target['path'], target['name']))
            if data_target.startswith('//'):
                warning("Test data not in the same directory with BUILD file")
                data_target = data_target[2:]
                os.symlink(os.path.abspath(data_target),
                        '%s/%s' % (self._runfiles_dir(target), link_name))
            else:
                os.symlink(os.path.abspath("%s/%s" % (target['path'], data_target)),
                       '%s/%s' % (self._runfiles_dir(target), link_name))

    def _clean_test_target(self, target):
        """clean the test target environment. """
        profile_link_name = os.path.basename(self.build_dir)
        profile_link_path = os.path.join(self._runfiles_dir(target), profile_link_name)
        if os.path.exists(profile_link_path):
            os.remove(profile_link_path)

    def _clean_test_env(self):
        """clean test environment. """
        for target in self.targets.values():
            if not (target['type'] == 'cc_test' or
                    target['type'] == 'dynamic_cc_test'):
                continue
            self._clean_test_target(target)

    def run_target(self, target_key):
        """Run one single target. """
        target = self.targets.get(target_key, {})
        if not target:
            error_exit("target %s:%s is not in the target databases" % (
                       target_key[0], target_key[1]))
        if target['type'] not in self.run_list:
            error_exit("target %s:%s is not a target that could run" % (
                       target_key[0], target_key[1]))
        self._prepare_run_env(target)
        old_pwd = get_cwd()
        cmd = "%s " % os.path.abspath(self._test_executable(target))
        if self.options.runargs:
            cmd += "%s" % self.options.runargs
        info("it will run '%s' " % cmd )
        sys.stdout.flush()

        target_dir = os.path.dirname(self._test_executable(target))
        os.chdir(target_dir)
        run_env = dict(os.environ)
        run_env['LD_LIBRARY_PATH'] = target_dir
        p = subprocess.Popen(cmd,
                             env=run_env,
                             shell=True)
        p.wait()
        os.chdir(old_pwd)
        return p.returncode

    def _get_test_target_md5sum(self, target):
        """Get test target md5sum. """
        related_file_list = []
        related_file_data_list = []
        test_file_name = os.path.abspath(self._test_executable(target))
        if os.path.exists(test_file_name):
            related_file_list.append(test_file_name)

        if target['type'] == 'dynamic_cc_test':
            target_key = (target['path'], target['name'])
            for dep in self.target_database.get(target_key, {}).get('deps', []):
                dep_target = self.target_database.get(dep, {})
                if 'cc_library' in dep_target.get('type', ''):
                    lib_name = 'lib%s.so' % dep_target['name']
                    lib_path = os.path.join(self.build_dir,
                                            dep_target['path'],
                                            lib_name)
                    abs_lib_path = os.path.abspath(lib_path)
                    if os.path.exists(abs_lib_path):
                        related_file_list.append(abs_lib_path)

        for i in target['options']['testdata']:
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
                data_target_path = os.path.abspath("%s/%s" % (
                                                   target['path'], data_target))
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

    def _get_inctest_run_list(self):
        """Get incremental test run list. """
        for target in self.targets.values():
            if not (target['type'] == 'cc_test' or
                    target['type'] == 'dynamic_cc_test'):
                continue
            target_key = "%s:%s" % (target['path'], target['name'])
            test_file_name = os.path.abspath(self._test_executable(target))
            self.cur_target_dict[test_file_name] = self._get_test_target_md5sum(target)
            if self.run_all:
                self.tests_run_map[target_key] = {
                        'runfile'  : test_file_name,
                        'result'   : '',
                        'reason'   : self.run_all_reason,
                        'costtime' : 0}
                continue

            old_md5sum = self.target_dict.get(test_file_name, None)
            new_md5sum = self.cur_target_dict[test_file_name]
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
                        'runfile'  : test_file_name,
                        'result'   : '',
                        'reason'   : reason,
                        'costtime' : 0}

        # Append old md5sum that not existed into new
        old_keys = set(self.target_dict.keys())
        new_keys = set(self.cur_target_dict.keys())
        diff_keys = old_keys.difference(new_keys)
        for key in list(diff_keys):
            self.cur_target_dict[key] = self.target_dict[key]

    def _check_inctest_md5sum_file(self):
        """check the md5sum file size, remove it when it is too large.
           It is 2G by default.
        """
        if os.path.exists(self.inctest_md5_file):
            if os.path.getsize(self.inctest_md5_file) > 2*1024*1024*1024:
                warning("Will remove the md5sum file for incremental test "
                        "for it is oversized"
                        )
                os.remove(self.inctest_md5_file)

    def _write_inctest_md5sum(self):
       """write md5sum to file. """
       f = open(self.inctest_md5_file, "w")
       print >> f, str(self.cur_testarg_dict)
       print >> f, str(self.cur_env_dict)
       print >> f, str(self.cur_target_dict)
       print >> f, str(self.this_inctest_time_dict)
       f.close()
       self._check_inctest_md5sum_file()

    def _write_tests_detail_map(self):
        """write the tests detail map for further use. """
        f = open(self.tests_detail_file, "w")
        print >> f, str(self.tests_run_map)
        f.close()

    def _show_tests_detail(self):
        """show the tests detail after scheduling them. """
        sort_buf = []
        for key in self.tests_run_map.keys():
            costtime = self.tests_run_map.get(key, {}).get('costtime', 0)
            sort_buf.append((key, costtime))
        sort_buf.sort(key=lambda x : x[1])

        if self.tests_run_map.keys():
            info("%s Testing detail %s" %(self.title_str, self.title_str))
        for key, costtime in sort_buf:
            reason = self.tests_run_map.get(key, {}).get('reason', 'UNKNOWN')
            result = self.tests_run_map.get(key, {}).get('result',
                                                         'INTERRUPTED')
            if 'SIG' in result:
                result = "with %s" % result
            print info_str("%s triggered by %s, exit(%s), cost %.2f s" % (
                           key, reason, result, costtime))

    def _finish_tests(self):
        """finish some work before return from runner. """
        self._write_inctest_md5sum()
        if hasattr(self.options, 'show_details') and self.options.show_details:
            self._write_tests_detail_map()
            if not self.run_all:
                self._show_skipped_tests_detail()
                self._show_skipped_tests_summary()
            self._show_tests_detail()
        elif not self.run_all:
            self._show_skipped_tests_summary()

    def _show_skipped_tests_detail(self):
        """show tests skipped. """
        if not self.skipped_tests:
            return
        self.skipped_tests.sort()
        info("skipped tests")
        for target_key in self.skipped_tests:
            print "%s:%s" % (target_key[0], target_key[1])

    def _show_skipped_tests_summary(self):
        """show tests skipped summary. """
        info("%d tests skipped when doing incremental test" % len(self.skipped_tests))
        info("to run all tests, please specify --full-test argument")

    def run(self):
        """Run all the cc_test target programs. """
        failed_targets = []
        self._get_inctest_run_list()
        tests_run_list = []
        old_pwd = get_cwd()
        for target in self.targets.values():
            if not (target['type'] == 'cc_test' or
                    target['type'] == 'dynamic_cc_test'):
                continue
            if (not self.run_all) and target not in self.inctest_run_list:
                if not target.get('options', {}).get('always_run', False):
                    self.skipped_tests.append((target['path'], target['name']))
                    continue
            self._prepare_test_env(target)
            cmd = "%s --gtest_output=xml" % os.path.abspath(self._test_executable(target))
            if self.options.testargs:
                cmd = "%s %s" % (cmd, self.options.testargs)

            sys.stdout.flush() # make sure output before scons if redirected

            test_env = dict(os.environ)
            test_env['LD_LIBRARY_PATH'] = self._runfiles_dir(target)
            test_env['GTEST_COLOR'] = 'yes' if blade_util.color_enabled else 'no'
            test_env['HEAPCHECK'] = target.get('options', {}).get('heap_check', '')
            tests_run_list.append((target,
                                   self._runfiles_dir(target),
                                   test_env,
                                   cmd))
        concurrent_jobs = 0
        if hasattr(self.options, 'test_jobs'):
            concurrent_jobs = self.options.test_jobs
        scheduler = TestScheduler(tests_run_list,
                                  concurrent_jobs,
                                  self.tests_run_map)
        scheduler.schedule_jobs()

        os.chdir(old_pwd)
        self._clean_test_env()
        info("%s Testing Summary %s" % (self.title_str, self.title_str))
        info("Run %d test targets" % scheduler.num_of_run_tests)

        failed_targets = scheduler.failed_targets
        if failed_targets:
            info("%d tests failed:" % len(failed_targets))
            for i in failed_targets:
                print "%s/%s, exit code: %s" % (
                    i["path"], i["name"], i["test_exit_code"])
                test_file_name = os.path.abspath(self._test_executable(i))
                # Do not skip failed test by default
                if self.cur_target_dict.has_key(test_file_name):
                    self.cur_target_dict[test_file_name] = (0, 0)
            info("%d tests passed" % (
                scheduler.num_of_run_tests - len(failed_targets)))
            self._finish_tests()
            return 1
        else:
            info("All tests passed!")
            self._finish_tests()
            return 0
