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

import os
import shutil
import subprocess
import sys

from blade import config
from blade import console
from blade.blade_util import environ_add_path


class BinaryRunner(object):
    """BinaryRunner. """

    def __init__(self, options, target_database, build_targets):
        """Init method. """
        from blade import build_manager
        self._build_targets = build_targets
        self.build_dir = build_manager.instance.get_build_dir()
        self.options = options
        self.run_list = ['cc_binary',
                         'cc_test',
                         'java_binary',
                         'java_test',
                         'py_binary',
                         'py_test',
                         'scala_test',
                         'sh_test']
        self.target_database = target_database

    def _executable(self, target):
        """Returns the executable path. """
        return os.path.join(self.build_dir, target.path, target.name)

    def _runfiles_dir(self, target):
        """Returns runfiles dir. """
        return '%s.runfiles' % self._executable(target)

    def _get_prebuilt_files(self, target):
        """Get prebuilt files for one target that it depends. """
        file_list = []
        for dep in target.expanded_deps:
            dep_target = self.target_database[dep]
            if dep_target.type == 'prebuilt_cc_library':
                prebuilt_file = dep_target.file_and_link
                if prebuilt_file:
                    file_list.append(prebuilt_file)
        return file_list

    def __check_test_data_dest(self, target, dest, dest_list):
        """Check whether the destination of test data is valid or not. """
        dest_norm = os.path.normpath(dest)
        if dest in dest_list:
            console.error_exit('Ambiguous testdata of %s: %s, exit...' % (
                target.fullname, dest))
        for item in dest_list:
            item_norm = os.path.normpath(item)
            if len(dest_norm) >= len(item_norm):
                long_path, short_path = dest_norm, item_norm
            else:
                long_path, short_path = item_norm, dest_norm
            if long_path.startswith(short_path) and long_path[len(short_path)] == '/':
                target.error_exit('"%s" could not exist with "%s" in testdata' % (dest, item))

    def _prepare_env(self, target):
        """Prepare the test environment. """
        runfiles_dir = self._runfiles_dir(target)
        shutil.rmtree(runfiles_dir, ignore_errors=True)
        os.mkdir(runfiles_dir)
        # Make a symbolic link of build_dir because dynamic linked binary need to load shared
        # libraries from this path
        build_dir_name = os.path.basename(self.build_dir)
        os.symlink(os.path.abspath(self.build_dir),
                   os.path.join(runfiles_dir, build_dir_name))

        # Also make symbolic links for prebuilt shared libraries
        for prebuilt_file in self._get_prebuilt_files(target):
            src = os.path.abspath(prebuilt_file[0])
            dst = os.path.join(runfiles_dir, prebuilt_file[1])
            if os.path.lexists(dst):
                console.warning('Trying to make duplicate prebuilt symlink:\n'
                                '%s -> %s\n'
                                '%s -> %s already exists\n'
                                'skipped, should check duplicate prebuilt '
                                'libraries'
                                % (dst, src, dst, os.path.realpath(dst)))
                continue
            os.symlink(src, dst)

        self._prepare_test_data(target)
        run_env = dict(os.environ)
        environ_add_path(run_env, 'LD_LIBRARY_PATH', runfiles_dir)
        run_lib_paths = config.get_item('cc_binary_config', 'run_lib_paths')
        if run_lib_paths:
            for path in run_lib_paths:
                if path.startswith('//'):
                    path = path[2:]
                path = os.path.abspath(path)
                environ_add_path(run_env, 'LD_LIBRARY_PATH', path)
        java_home = config.get_item('java_config', 'java_home')
        if java_home:
            java_home = os.path.abspath(java_home)
            environ_add_path(run_env, 'PATH', os.path.join(java_home, 'bin'))

        return run_env

    def _prepare_test_data(self, target):
        if 'testdata' not in target.data:
            return
        runfiles_dir = self._runfiles_dir(target)
        dest_list = []
        for i in target.data['testdata']:
            if isinstance(i, tuple):
                src, dest = i
            else:
                src = dest = i
            if '..' in src:
                console.warning('//%s: Relative path is not allowed in testdata source. '
                                'Ignored %s.' % (target.fullname, src))
                continue
            if src.startswith('//'):
                src = src[2:]
            else:
                src = os.path.join(target.path, src)
            if dest.startswith('//'):
                dest = dest[2:]
            dest = os.path.normpath(dest)
            self.__check_test_data_dest(target, dest, dest_list)
            dest_list.append(dest)
            dest_path = os.path.join(runfiles_dir, dest)
            if os.path.exists(dest_path):
                console.warning('//%s: "%s" already existed, could not prepare testdata.' %
                                (target.fullname, dest))
                continue
            try:
                os.makedirs(os.path.dirname(dest_path))
            except OSError:
                pass

            if os.path.isfile(src):
                shutil.copy2(src, dest_path)
            elif os.path.isdir(src):
                shutil.copytree(src, dest_path)

        self._prepare_extra_test_data(target)

    def _prepare_extra_test_data(self, target):
        """Prepare extra test data specified in the .testdata file if it exists. """
        testdata = os.path.join(self.build_dir, target.path,
                                '%s.testdata' % target.name)
        if os.path.isfile(testdata):
            runfiles_dir = self._runfiles_dir(target)
            for line in open(testdata):
                data = line.strip().split()
                if len(data) == 1:
                    src, dst = data[0], ''
                else:
                    src, dst = data[0], data[1]
                dst = os.path.join(runfiles_dir, dst)
                dst_dir = os.path.dirname(dst)
                if not os.path.isdir(dst_dir):
                    os.makedirs(dst_dir)
                shutil.copy2(src, dst)

    def _clean_target(self, target):
        """Clean the executive environment."""
        build_dir_name = os.path.basename(self.build_dir)
        link_path = os.path.join(self._runfiles_dir(target), build_dir_name)
        if os.path.exists(link_path):
            os.remove(link_path)

    def _clean_for_coverage(self):
        """Clean executive environment for coverage generating."""
        for target in self._build_targets.values():
            self._clean_target(target)

    def run_target(self, target_name):
        """Run one single target."""
        target_key = tuple(target_name.split(':'))
        target = self._build_targets[target_key]
        if target.type not in self.run_list:
            target.error_exit('is not a executable target')
        run_env = self._prepare_env(target)
        cmd = [os.path.abspath(self._executable(target))] + self.options.args
        shell = target.data.get('run_in_shell', False)
        if shell:
            cmd = subprocess.list2cmdline(cmd)
        console.info("Run '%s'" % cmd)
        sys.stdout.flush()

        p = subprocess.Popen(cmd, env=run_env, close_fds=True, shell=shell)
        p.wait()
        self._clean_for_coverage()
        return p.returncode
