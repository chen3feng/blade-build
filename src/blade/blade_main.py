# Copyright 2011 Tencent Inc.
#
# Authors: Huan Yu <huanyu@tencent.com>
#          Feng Chen <phongchen@tencent.com>
#          Yi Wang <yiwang@tencent.com>
#          Chong Peng <michaelpeng@tencent.com>

"""
Main entrence of blade.
"""

from __future__ import absolute_import
from __future__ import print_function

import cProfile
import errno
import json
import os
import pstats
import re
import signal
import subprocess
import time
import traceback
from string import Template

from blade import build_attributes
from blade import build_manager
from blade import command_line
from blade import config
from blade import console
from blade import target_pattern
from blade.blade_util import find_blade_root_dir
from blade.blade_util import get_cwd, to_string
from blade.blade_util import lock_file, unlock_file


def lock_workspace(build_dir):
    _BUILDING_LOCK_FILE = '.blade.building.lock'
    lock_file_fd, ret_code = lock_file(os.path.join(build_dir, _BUILDING_LOCK_FILE))
    if lock_file_fd == -1:
        if ret_code == errno.EAGAIN:
            console.fatal('There is already an active building in current workspace.')
        else:
            console.fatal('Lock exception, please try it later.')
    return lock_file_fd


def unlock_workspace(lock_file_fd):
    unlock_file(lock_file_fd)


def load_config(options, root_dir):
    """Load the configuration file and parse."""
    # Init global build attributes
    build_attributes.initialize(options)
    config.load_files(root_dir, options.load_local_config)


def setup_build_dir(options):
    build_path_format = config.get_item('global_config', 'build_path_template')
    s = Template(build_path_format)
    build_dir = s.substitute(bits=options.bits, profile=options.profile)
    if not os.path.exists(build_dir):
        os.mkdir(build_dir)
    try:
        os.remove('blade-bin')
    except os.error:
        pass
    os.symlink(os.path.abspath(build_dir), 'blade-bin')
    return build_dir


def get_source_dirs():
    """Get workspace dir and working dir relative to workspace dir."""
    working_dir = get_cwd()
    root_dir = find_blade_root_dir(working_dir)
    working_dir = os.path.relpath(working_dir, root_dir)

    return root_dir, working_dir


def setup_console(options):
    if options.color != 'auto':
        console.enable_color(options.color == 'yes')
    console.set_verbosity(options.verbosity)


def setup_log(build_dir, options):
    log_file = os.path.join(build_dir, 'blade.log')
    console.set_log_file(log_file)


def generate_scm_svn():
    url = revision = 'unknown'
    p = subprocess.Popen('svn info', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    stdout = to_string(stdout)
    stderr = to_string(stderr)
    if p.returncode != 0:
        console.debug('Failed to generate svn scm: %s' % stderr)
    else:
        for line in stdout.splitlines():
            if line.startswith('URL: '):
                url = line.strip().split()[-1]
            if line.startswith('Revision: '):
                revision = line.strip().split()[-1]
                break

    return url, revision


def generate_scm_git():
    url = revision = 'unknown'

    def git(cmd):
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        stdout = to_string(stdout)
        stderr = to_string(stderr)
        if p.returncode != 0:
            console.debug('Failed to generate git scm: %s' % stderr)
            return ''
        return stdout

    out = git('git rev-parse HEAD')
    if out:
        revision = out.strip()
    out = git('git remote -v')
    # $ git remote -v
    # origin  https://github.com/chen3feng/blade-build.git (fetch)
    # origin  https://github.com/chen3feng/blade-build.git (push)
    if out:
        url = out.splitlines()[0].split()[1]
        # Remove userinfo (such as username and password) from url, if any.
        url = re.sub(r'(?<=://).*:.*@', '', url)
    return url, revision


def generate_scm(build_dir):
    if os.path.isdir('.git'):
        url, revision = generate_scm_git()
    elif os.path.isdir('.svn'):
        url, revision = generate_scm_svn()
    else:
        console.debug('Unknown scm.')
        return
    path = os.path.join(build_dir, 'scm.json')
    with open(path, 'w') as f:
        json.dump({
            'revision': revision,
            'url': url,
        }, f)


def adjust_config_by_options(config, options):
    # Common options between config and command line
    common_options = ('debug_info_level', 'backend_builder',
                      'build_jobs', 'test_jobs', 'run_unrepaired_tests')
    for name in common_options:
        value = getattr(options, name, None)
        if value:
            config.global_config(**{name: value})


def _check_error_log(stage):
    error_count = console.error_count()
    if error_count > 0:
        console.error('There are %s errors in the %s stage' % (error_count, stage))
        return 1
    return 0


def run_subcommand(command, options, targets, blade_path, root_dir, build_dir, working_dir):
    """Run particular commands before loading"""
    # The 'dump' command is special, some kind of dump items should be ran before loading.
    if command == 'dump' and options.dump_config:
        output_file_name = os.path.join(working_dir, options.dump_to_file)
        config.dump(output_file_name)
        return _check_error_log('dump')

    load_targets = targets
    if command == 'query' and options.dependents:
        # In query dependents mode, we must load all targets in workspace to get a whole view
        load_targets = ['.:...']
    build_manager.initialize(blade_path, targets, load_targets,
                             root_dir, build_dir, working_dir,
                             command, options)

    # Build the targets
    build_manager.instance.load_targets()
    if _check_error_log('load'):
        return 1
    if options.stop_after == 'load':
        return 0

    build_manager.instance.analyze_targets()
    if _check_error_log('analyze'):
        return 1
    if options.stop_after == 'analyze':
        return 0

    build_manager.instance.generate()
    if _check_error_log('generate'):
        return 1
    if options.stop_after == 'generate':
        return 0

    # Switch case due to different sub command
    action = {
        'build': build_manager.instance.build,
        'clean': build_manager.instance.clean,
        'dump': build_manager.instance.dump,
        'query': build_manager.instance.query,
        'run': build_manager.instance.run,
        'test': build_manager.instance.test,
    }[command]
    returncode = action()
    if returncode != 0:
        return returncode
    return _check_error_log(command)


def run_subcommand_profile(command, options, targets, blade_path, root_dir, build_dir, working_dir):
    pstats_file = os.path.join(build_dir, 'blade.pstats')
    # NOTE: can't use an plain int variable to receive exit_code
    # because in python int is an immutable object, assign to it in the runctx
    # wll not modify the local exit_code.
    # so we use a mutable object list to obtain the return value of run_subcommand
    exit_code = [-1]
    cProfile.runctx("exit_code[0] = run_subcommand(command, options, targets, blade_path, root_dir, build_dir, working_dir)",
                    globals(), locals(), pstats_file)
    p = pstats.Stats(pstats_file)
    p.sort_stats('cumulative').print_stats(20)
    p.sort_stats('time').print_stats(20)
    console.output('Binary profile file `%s` is also generated, '
                   'you can use `gprof2dot` or `vprof` to convert it to graph, eg:' % pstats_file)
    console.output('  gprof2dot.py -f pstats --color-nodes-by-selftime %s'
                   ' | dot -T pdf -o blade.pdf' % pstats_file)
    return exit_code[0]


def _main(blade_path, argv):
    """The main entry of blade."""
    command, options, targets = command_line.parse(argv)
    setup_console(options)

    root_dir, working_dir = get_source_dirs()
    if root_dir != working_dir:
        # This message is required by vim quickfix mode if pwd is changed during
        # the building, DO NOT change the pattern of this message.
        if options.verbosity != 'quiet':
            print("Blade: Entering directory `%s'" % root_dir)
        os.chdir(root_dir)

    load_config(options, root_dir)
    adjust_config_by_options(config, options)
    if _check_error_log('config'):
        return 1

    if not targets:
        targets = ['.']
    targets = target_pattern.normalize_list(targets, working_dir)

    build_dir = setup_build_dir(options)
    setup_log(build_dir, options)

    generate_scm(build_dir)

    lock_file_fd = lock_workspace(build_dir)
    try:
        run_fn = run_subcommand_profile if options.profiling else run_subcommand
        return run_fn(command, options, targets, blade_path, root_dir, build_dir, working_dir)
    finally:
        unlock_workspace(lock_file_fd)


def format_timedelta(seconds):
    """
    Format the time delta as human readable format such as '1h20m5s' or '5s' if it is short.
    """
    # We used to use the datetime.timedelta class, but its result such as
    #   Blade(info): cost time 00:05:30s
    # cause vim to create a new file named "Blade(info): cost time 00"
    # in vim QuickFix mode. So we use the new format now.
    mins = seconds // 60
    seconds %= 60
    hours = mins // 60
    mins %= 60
    if hours == 0 and mins == 0:
        return '%ss' % seconds
    if hours == 0:
        return '%sm%ss' % (mins, seconds)
    return '%sh%sm%ss' % (hours, mins, seconds)


def main(blade_path, argv):
    exit_code = 0
    try:
        start_time = time.time()
        exit_code = _main(blade_path, argv)
        cost_time = int(time.time() - start_time)
        if cost_time > 1:
            console.info('Cost time %s' % format_timedelta(cost_time))
    except SystemExit as e:
        # pylint misreport e.code as classobj
        exit_code = e.code
    except KeyboardInterrupt:
        console.error('KeyboardInterrupt')
        exit_code = -signal.SIGINT
    except:  # pylint: disable=bare-except
        exit_code = 1
        console.error(traceback.format_exc())
    if exit_code != 0:
        console.error('Failure')
    return exit_code
