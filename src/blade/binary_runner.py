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
import shutil
import subprocess
import sys

import blade
import cc_targets
import console
import configparse

from blade_util import environ_add_path


class BinaryRunner(object):
    """BinaryRunner. """
    def __init__(self, targets, options, target_database):
        """Init method. """
        self.targets = targets
        self.build_dir = blade.blade.get_build_path()
        self.options = options
        self.run_list = ['cc_binary',
                         'cc_test']
        self.target_database = target_database

    def _executable(self, target):
        """Returns the executable path. """
        return '%s/%s/%s' % (self.build_dir, target.path, target.name)

    def _runfiles_dir(self, target):
        """Returns runfiles dir. """
        return './%s.runfiles' % (self._executable(target))

    def _prepare_run_env(self, target):
        """Prepare the run environment. """
        profile_link_name = os.path.basename(self.build_dir)
        target_dir = os.path.dirname(self._executable(target))
        lib_link = os.path.join(target_dir, profile_link_name)
        if os.path.exists(lib_link):
            os.remove(lib_link)
        os.symlink(os.path.abspath(self.build_dir), lib_link)

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

    def __check_link_name(self, link_name, link_name_list):
        """check the link name is valid or not. """
        link_name_norm = os.path.normpath(link_name)
        if link_name in link_name_list:
            return 'AMBIGUOUS', None
        long_path = ''
        short_path = ''
        for item in link_name_list:
            item_norm = os.path.normpath(item)
            if len(link_name_norm) >= len(item_norm):
                (long_path, short_path) = (link_name_norm, item_norm)
            else:
                (long_path, short_path) = (item_norm, link_name_norm)
            if long_path.startswith(short_path) and (
                    long_path[len(short_path)] == '/'):
                return 'INCOMPATIBLE', item
        else:
            return 'VALID', None

    def _prepare_env(self, target):
        """Prepare the test environment. """
        shutil.rmtree(self._runfiles_dir(target), ignore_errors=True)
        os.mkdir(self._runfiles_dir(target))
        # add build profile symlink
        profile_link_name = os.path.basename(self.build_dir)
        os.symlink(os.path.abspath(self.build_dir),
                   os.path.join(self._runfiles_dir(target), profile_link_name))

        # add pre build library symlink
        for prebuilt_file in self._get_prebuilt_files(target):
            src = os.path.abspath(prebuilt_file[0])
            dst = os.path.join(self._runfiles_dir(target), prebuilt_file[1])
            if os.path.lexists(dst):
                console.warning('trying to make duplicate prebuilt symlink:\n'
                                '%s -> %s\n'
                                '%s -> %s already exists\n'
                                'skipped, should check duplicate prebuilt '
                                'libraries'
                        % (dst, src, dst, os.path.realpath(dst)))
                continue
            os.symlink(src, dst)

        self._prepare_test_data(target)
        run_env = dict(os.environ)
        environ_add_path(run_env, 'LD_LIBRARY_PATH',
                         self._runfiles_dir(target))
        config = configparse.blade_config.get_config('cc_binary_config')
        run_lib_paths = config['run_lib_paths']
        if run_lib_paths:
            for path in run_lib_paths:
                if path.startswith('//'):
                    path = path[2:]
                path = os.path.abspath(path)
                environ_add_path(run_env, 'LD_LIBRARY_PATH', path)
        return run_env

    def _prepare_test_data(self, target):
        if 'testdata' not in target.data:
            return
        link_name_list = []
        for i in target.data['testdata']:
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
            if err_msg == 'AMBIGUOUS':
                console.error_exit('Ambiguous testdata of //%s:%s: %s, exit...' % (
                             target.path, target.name, link_name))
            elif err_msg == 'INCOMPATIBLE':
                console.error_exit('%s could not exist with %s in testdata of //%s:%s' % (
                           link_name, item, target.path, target.name))
            link_name_list.append(link_name)
            try:
                os.makedirs(os.path.dirname('%s/%s' % (
                        self._runfiles_dir(target), link_name)))
            except OSError:
                pass

            symlink_name = os.path.abspath('%s/%s' % (
                                self._runfiles_dir(target), link_name))
            symlink_valid = False
            if os.path.lexists(symlink_name):
                if os.path.exists(symlink_name):
                    symlink_valid = True
                    console.warning('%s already existed, could not prepare '
                                    'testdata for //%s:%s' % (
                                        link_name, target.path, target.name))
                else:
                    os.remove(symlink_name)
                    console.warning('%s already existed, but it is a broken '
                                    'symbolic link, blade will remove it and '
                                    'make a new one.' % link_name)
            if data_target.startswith('//'):
                data_target = data_target[2:]
                dest_data_file = os.path.abspath(data_target)
            else:
                dest_data_file = os.path.abspath('%s/%s' % (target.path, data_target))

            if not symlink_valid:
                os.symlink(dest_data_file,
                           '%s/%s' % (self._runfiles_dir(target), link_name))

    def _clean_target(self, target):
        """clean the test target environment. """
        profile_link_name = os.path.basename(self.build_dir)
        profile_link_path = os.path.join(self._runfiles_dir(target), profile_link_name)
        if os.path.exists(profile_link_path):
            os.remove(profile_link_path)

    def _clean_env(self):
        """clean test environment. """
        for target in self.targets.values():
            if target.type != 'cc_test':
                continue
            self._clean_target(target)

    def run_target(self, target_key):
        """Run one single target. """
        target = self.targets[target_key]
        if target.type not in self.run_list:
            console.error_exit('target %s:%s is not a target that could run' % (
                       target_key[0], target_key[1]))
        run_env = self._prepare_env(target)
        cmd = [os.path.abspath(self._executable(target))] + self.options.args
        console.info("'%s' will be ran" % cmd)
        sys.stdout.flush()

        p = subprocess.Popen(cmd, env=run_env, close_fds=True)
        p.wait()
        self._clean_env()
        return p.returncode
