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
import os
import pstats
import signal
import time
import traceback

from blade import build_attributes
from blade import build_manager
from blade import command_line
from blade import config
from blade import console
from blade import target_pattern
from blade import workspace


def load_config(options, root_dir):
    """Load the configuration file and parse."""
    # Init global build attributes
    build_attributes.initialize(options)
    config.load_files(root_dir, options.load_local_config)


def setup_console(options):
    if options.color != 'auto':
        console.enable_color(options.color == 'yes')
    console.set_verbosity(options.verbosity)


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


def run_subcommand(blade_path, command, options, ws, targets):
    """Run particular commands before loading"""
    # The 'dump' command is special, some kind of dump items should be ran before loading.
    if command == 'dump' and options.dump_config:
        output_file_name = os.path.join(ws.working_dir(), options.dump_to_file)
        config.dump(output_file_name)
        return _check_error_log('dump')

    load_targets = targets
    build_manager.initialize(blade_path, command, options, ws, targets)

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


def run_subcommand_profile(blade_path, command, options, ws, targets):
    pstats_file = os.path.join(ws.build_dir(), 'blade.pstats')
    # NOTE: can't use an plain int variable to receive exit_code
    # because in python int is an immutable object, assign to it in the runctx
    # wll not modify the local exit_code.
    # so we use a mutable object list to obtain the return value of run_subcommand
    exit_code = [-1]
    cProfile.runctx("exit_code[0] = run_subcommand(blade_path, command, options, ws, targets)",
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

    ws = workspace.initialize(options)
    load_config(options, ws.root_dir())
    ws.switch_to_root_dir()

    adjust_config_by_options(config, options)
    if _check_error_log('config'):
        return 1

    if not targets:
        targets = ['.']
    targets = target_pattern.normalize_list(targets, ws.working_dir())

    ws.setup_build_dir()

    lock_id = ws.lock()
    try:
        run_fn = run_subcommand_profile if options.profiling else run_subcommand
        return run_fn(blade_path, command, options, ws, targets)
    finally:
        ws.unlock(lock_id)


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
