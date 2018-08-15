# Copyright 2011 Tencent Inc.
#
# Authors: Huan Yu <huanyu@tencent.com>
#          Feng Chen <phongchen@tencent.com>
#          Yi Wang <yiwang@tencent.com>
#          Chong Peng <michaelpeng@tencent.com>

"""
 Blade is a software building system built upon SCons, but restricts
 the generality and flexibility of SCons to prevent unnecessary
 error-prone complexity.  With Blade, users wrote a BUILD file and
 put it in each of the source directory.  In each BUILD file, there
 could be one or more build rules, each has a TARGET NAME, source
 files and dependent targets.  Blade suports the following types of
 build rules:


    cc_binary         -- build an executable binary from C++ source
    cc_library        -- build a library from C++ source
    cc_plugin         -- build a plugin from C++ source
    cc_test           -- build a unittest binary from C++ source
    cc_benchmark      -- build a benchmark binary from C++ source
    gen_rule          -- used to specify a general building rule
    java_jar          -- build java jar from java source files
    lex_yacc_library  -- build a library from lex/yacc source
    proto_library     -- build a library from Protobuf source
    thrift_library    -- build a library from Thrift source
    fbthrift_library  -- build a library from Thrift source for Facebook's Thrift Cpp2
    resource_library  -- build resource library and gen header files
    swig_library      -- build swig library for python and java

 A target may depend on other target(s), where the dependency is
 transitive.  A dependent target is referred by a TARGET ID, which
 has either of the following forms:

   //<source_dir>:<target_name> -- target defined in <source_dir>/BUILD
   :<target_name>               -- target defined in the current BUILD file
   #<target_name>               -- target is a system library, e.g., pthread

 where <source_dir> is an absolute path rooted at the source tree and
 specifying where the BUILD file locates, <target_name> specifies a
 target in the BUILD file, and '//' denotes the root of the source tree.

 Users invoke Blade from the command line to build (or clean, or
 test) one or more rule/targets.  In the command line, a target id
 is specified in either of the following forms:

   <path>:<target_name> -- to build target defined in <path>/BUILD
   <path>               -- to build all targets defined in <path>/BUILD
   <path>/...           -- to build all targets in all BUILD files in
                           <path> and its desendant directories.

 Note that <path> in command line targets is an operating system
 path, which might be a relative path, but <source_dir> in a BUILD
 referring to a dependent target must be an absolute path, rooted at
 '//'.

 For example, the following command line

    blade build base mapreduce_lite/... parallel_svm:perf_test

 builds all targets in base/BUILD, all targets in all BUILDs under
 directory mapreduce_lite, and the target perf_test defined in
 parallel_svm/BUILD
"""


import cProfile
import datetime
import errno
import json
import os
import pstats
import signal
import subprocess
import sys
import time
import traceback
from string import Template

import blade
import build_attributes
import console
import config

from blade_util import find_blade_root_dir, find_file_bottom_up
from blade_util import get_cwd
from blade_util import lock_file, unlock_file
from command_args import CmdArguments


# Run target
_TARGETS = None


_BLADE_ROOT_DIR = None
_WORKING_DIR = None


def _normalize_target(target, working_dir):
    '''Normalize target from command line into canonical form.

    Target canonical form: dir:name
        dir: relative to blade_root_dir, use '.' for blade_root_dir
        name: name  if target is dir:name
              '*'   if target is dir
              '...' if target is dir/...
    '''
    if target.startswith('//'):
        target = target[2:]
    elif target.startswith('/'):
        console.error_exit('Invalid target "%s" starting from root path.' % target)
    else:
        if working_dir != '.':
            target = os.path.join(working_dir, target)

    if ':' in target:
        path, name = target.rsplit(':', 1)
    else:
        if target.endswith('...'):
            path = target[:-3]
            name = '...'
        else:
            path = target
            name = '*'
    path = os.path.normpath(path)
    return '%s:%s' % (path, name)


def normalize_targets(targets, blade_root_dir, working_dir):
    if not targets:
        targets = ['.']
    return [_normalize_target(target, working_dir) for target in targets]


# For our opensource projects (toft, thirdparty, foxy etc.), we mkdir a project
# dir , add subdirs are github repos, here we need to fix out the git ROOT for
# each build target
def find_scm_root(target, scm):
    scm_dir = find_file_bottom_up('.' + scm, target)
    if not scm_dir:
        return ''
    return os.path.dirname(scm_dir)


def _target_in_dir(path, dirtotest):
    '''Test whether path is in the dirtotest'''
    if dirtotest == '.':
        return True
    return os.path.commonprefix([path, dirtotest]) == dirtotest


def split_targets_into_scm_root(targets, working_dir):
    '''Split all targets by scm root dirs'''
    scm_root_dirs = {}  # scm_root_dir : (scm_type, target_dirs)
    checked_dir = set()
    scms = ('svn', 'git')
    for target in targets:
        target_dir = target.split(':')[0]
        if target_dir in checked_dir:
            continue
        checked_dir.add(target_dir)
        # Only check targets under working dir
        if not _target_in_dir(target_dir, working_dir):
            continue
        for scm in scms:
            scm_root = find_scm_root(target_dir, scm)
            if scm_root:
                rel_target_dir = os.path.relpath(target_dir, scm_root)
                if scm_root in scm_root_dirs:
                    scm_root_dirs[scm_root][1].append(rel_target_dir)
                else:
                    scm_root_dirs[scm_root] = (scm, [rel_target_dir])
    return scm_root_dirs


def _get_changed_files(targets, blade_root_dir, working_dir):
    scm_root_dirs = split_targets_into_scm_root(targets, working_dir)
    changed_files = set()
    for scm_root, (scm, dirs) in scm_root_dirs.iteritems():
        try:
            os.chdir(scm_root)
            if scm == 'svn':
                output = os.popen('svn st %s' % ' '.join(dirs)).read().split('\n')
            elif scm == 'git':
                status_cmd = 'git status --porcelain %s' % ' '.join(dirs)
                output = os.popen(status_cmd).read().split('\n')
            for f in output:
                seg = f.strip().split()
                if not seg or seg[0] != 'M' and seg[0] != 'A':
                    continue
                f = seg[-1]
                fullpath = os.path.join(scm_root, f)
                changed_files.add(fullpath)
        finally:
            os.chdir(blade_root_dir)
    return changed_files


def _check_code_style(targets):
    cpplint = config.get_item('cc_config', 'cpplint')
    if not cpplint:
        console.info('cpplint disabled')
        return 0
    changed_files = _get_changed_files(targets, _BLADE_ROOT_DIR, _WORKING_DIR)
    if not changed_files:
        return 0
    console.info('Begin to check code style for changed source code')
    p = subprocess.Popen(('%s %s' % (cpplint, ' '.join(changed_files))), shell=True)
    try:
        p.wait()
        if p.returncode != 0:
            if p.returncode == 127:
                msg = ("Can't execute '{0}' to check style, you can config the "
                       "'cpplint' option to be a valid cpplint path in the "
                       "'cc_config' section of blade.conf or BLADE_ROOT, or "
                       "make sure '{0}' command is correct.").format(cpplint)
            else:
                msg = 'Please fixing style warnings before submitting the code!'
            console.warning(msg)
    except KeyboardInterrupt, e:
        console.error(str(e))
        return 1
    return 0


def _run_native_builder(cmdstr):
    p = subprocess.Popen(cmdstr, shell=True)
    try:
        p.wait()
        return p.returncode
    except:  # KeyboardInterrupt
        return 1


def native_builder_options(options):
    '''Setup some options which are same in different native builders. '''
    build_options = []
    if options.dry_run:
        build_options.append('-n')
    if options.native_builder_options:
        build_options.append(options.native_builder_options)
    return build_options


def _scons_build(options):
    cmd = ['scons']
    cmd += native_builder_options(options)
    cmd.append('-j%s' % (options.jobs or blade.blade.parallel_jobs_num()))
    cmd += ['--duplicate=soft-copy', '--cache-show']
    if options.keep_going:
        cmd.append('-k')
    if console.verbosity_compare(options.verbosity, 'quiet') <= 0:
        cmd.append('-s')
    cmdstr = subprocess.list2cmdline(cmd)
    return _run_native_builder(cmdstr)


def _ninja_build(options):
    cmd = ['ninja']
    cmd += native_builder_options(options)
    # if options.jobs:
        # Unlike scons, ninja enable parallel building defaultly,
        # so only set it when user specified it explicitly.
        # cmd.append('-j%s' % options.jobs)
    cmd.append('-j%s' % (options.jobs or blade.blade.parallel_jobs_num()))
    if options.keep_going:
        cmd.append('-k0')
    if console.verbosity_compare(options.verbosity, 'verbose') >= 0:
        cmd.append('-v')
    cmdstr = subprocess.list2cmdline(cmd)
    if console.verbosity_compare(options.verbosity, 'quiet') <= 0:
        # Filter out description message such as '[1/123] CC xxx.cc'
        cmdstr += r' | sed -e "/^\[[0-9]*\/[0-9]*\] /d"'
    return _run_native_builder(cmdstr)


def build(options):
    _check_code_style(_TARGETS)
    console.info('building...')
    console.flush()
    if config.get_item('global_config', 'native_builder') == 'ninja':
        returncode = _ninja_build(options)
    else:
        returncode = _scons_build(options)
    if returncode != 0:
        console.error('building failure.')
        return returncode
    if not blade.blade.verify():
        console.error('building failure.')
        return 1
    console.info('building done.')
    return 0


def run(options):
    ret = build(options)
    if ret != 0:
        return ret
    run_target = _TARGETS[0]
    return blade.blade.run(run_target)


def test(options):
    if not options.no_build:
        ret = build(options)
        if ret != 0:
            return ret
    return blade.blade.test()


def clean(options):
    console.info('cleaning...(hint: please specify --generate-dynamic to '
                 'clean your so)')
    native_builder = config.get_item('global_config', 'native_builder')
    cmd = [native_builder]
    # cmd += native_builder_options(options)
    if native_builder == 'ninja':
        cmd += ['-t', 'clean']
    else:
        cmd += ['--duplicate=soft-copy', '-c', '-s', '--cache-show']
    cmdstr = subprocess.list2cmdline(cmd)
    returncode = _run_native_builder(cmdstr)
    console.info('cleaning done.')
    return returncode


def query(options):
    return blade.blade.query(_TARGETS)


def lock_workspace():
    lock_file_fd, ret_code = lock_file('.Building.lock')
    if lock_file_fd == -1:
        if ret_code == errno.EAGAIN:
            console.error_exit(
                    'There is already an active building in current source tree.')
        else:
            console.error_exit('Lock exception, please try it later.')
    return lock_file_fd


def unlock_workspace(lock_file_fd):
    unlock_file(lock_file_fd)


def parse_command_line():
    parsed_command_line = CmdArguments()
    command = parsed_command_line.get_command()
    options = parsed_command_line.get_options()
    targets = parsed_command_line.get_targets()
    return command, options, targets


def load_config(options, blade_root_dir):
    """load the configuration file and parse. """
    # Init global build attributes
    build_attributes.initialize(options)
    config.load_files(blade_root_dir, options.load_local_config)


def setup_build_dir(options):
    build_path_format = config.get_item('global_config', 'build_path_template')
    s = Template(build_path_format)
    build_dir = s.substitute(bits=options.m, profile=options.profile)
    if not os.path.exists(build_dir):
        os.mkdir(build_dir)
    return build_dir


def get_source_dirs():
    '''Get workspace dir and working dir relative to workspace dir'''
    working_dir = get_cwd()
    blade_root_dir = find_blade_root_dir(working_dir)
    working_dir = os.path.relpath(working_dir, blade_root_dir)

    return blade_root_dir, working_dir


def setup_log(build_dir, options):
    log_file = os.path.join(build_dir, 'blade.log')
    console.set_log_file(log_file)
    console.set_verbosity(options.verbosity)


def generate_scm(build_dir):
    # TODO(wentingli): Add git scm
    p = subprocess.Popen('svn info', shell=True,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate()
    if p.returncode != 0:
        console.debug('Failed to generate scm: %s' % stderr)
        return
    revision = url = 'unknown'
    for line in stdout.splitlines():
        if line.startswith('URL: '):
            url = line.strip().split()[-1]
        if line.startswith('Revision: '):
            revision = line.strip().split()[-1]
            break
    path = os.path.join(build_dir, 'scm.json')
    with open(path, 'w') as f:
        json.dump({
            'revision' : revision,
            'url' : url,
        }, f)


def adjust_config_by_options(config, options):
    for name in ('debug_info_level', 'native_builder'):
        value = getattr(options, name, None)
        if value:
            config.global_config(**{name: value})


def clear_build_script():
    for script in ('SConstruct', 'build.ninja'):
        script = os.path.join(_BLADE_ROOT_DIR, script)
        try:
            os.remove(script)
        except OSError:
            pass


def run_subcommand(command, options, targets, blade_path, build_dir):
    if command == 'query' and options.depended:
        targets = ['.:...']
    blade.blade = blade.Blade(targets,
                              blade_path,
                              _WORKING_DIR,
                              build_dir,
                              _BLADE_ROOT_DIR,
                              options,
                              command)

    # Build the targets
    blade.blade.load_targets()
    if options.stop_after == 'load':
        return 0
    blade.blade.analyze_targets()
    if options.stop_after == 'analyze':
        return 0
    blade.blade.generate()
    if options.stop_after == 'generate':
        return 0

    # Switch case due to different sub command
    action = {
        'build': build,
        'run': run,
        'test': test,
        'clean': clean,
        'query': query
    }[command]
    try:
        returncode = action(options)
    finally:
        clear_build_script()

    return returncode


def run_subcommand_profile(command, options, targets, blade_path, build_dir):
    pstats_file = os.path.join(build_dir, 'blade.pstats')
    # NOTE: can't use an plain int variable to receive exit_code
    # because in python int is an immutable object, assign to it in the runctx
    # wll not modify the local exit_code.
    # so we use a mutable object list to obtain the return value of run_subcommand
    exit_code = [-1]
    cProfile.runctx("exit_code[0] = run_subcommand(command, options, targets, blade_path, build_dir)",
                    globals(), locals(), pstats_file)
    p = pstats.Stats(pstats_file)
    p.sort_stats('cumulative').print_stats(20)
    p.sort_stats('time').print_stats(20)
    console.info('Binary result file %s is also generated, '
                 'you can use gprof2dot or vprof to convert it to graph' % pstats_file)
    console.info('gprof2dot.py -f pstats --color-nodes-by-selftime %s'
                 ' | dot -T pdf -o blade.pdf' % pstats_file)
    return exit_code[0]


def _main(blade_path):
    """The main entry of blade. """
    command, options, targets = parse_command_line()

    global _BLADE_ROOT_DIR
    global _WORKING_DIR
    _BLADE_ROOT_DIR, _WORKING_DIR = get_source_dirs()
    if _BLADE_ROOT_DIR != _WORKING_DIR:
        # This message is required by vim quickfix mode if pwd is changed during
        # the building, DO NOT change the pattern of this message.
        if options.verbosity != 'quiet':
            print "Blade: Entering directory `%s'" % _BLADE_ROOT_DIR
        os.chdir(_BLADE_ROOT_DIR)

    load_config(options, _BLADE_ROOT_DIR)
    adjust_config_by_options(config, options)

    build_dir = setup_build_dir(options)
    setup_log(build_dir, options)

    global _TARGETS
    targets = normalize_targets(targets, _BLADE_ROOT_DIR, _WORKING_DIR)
    _TARGETS = targets
    generate_scm(build_dir)

    lock_file_fd = lock_workspace()
    try:
        if options.profiling:
            return run_subcommand_profile(command, options, targets, blade_path, build_dir)
        return run_subcommand(command, options, targets, blade_path, build_dir)
    finally:
        unlock_workspace(lock_file_fd)


def main(blade_path):
    exit_code = 0
    try:
        start_time = time.time()
        exit_code = _main(blade_path)
        cost_time = int(time.time() - start_time)
        if exit_code == 0:
            console.info('success')
        console.info('cost time is %ss' % datetime.timedelta(seconds=cost_time))
    except SystemExit, e:
        exit_code = e.code
    except KeyboardInterrupt:
        console.error_exit('keyboard interrupted', -signal.SIGINT)
    except:
        console.error_exit(traceback.format_exc())
    sys.exit(exit_code)
