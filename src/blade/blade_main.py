# Copyright 2011 Tencent Inc.
#
# Authors: Huan Yu <huanyu@tencent.com>
#          Feng Chen <phongchen@tencent.com>
#          Yi Wang <yiwang@tencent.com>
#          Chong Peng <michaelpeng@tencent.com>

"""
 Blade is a software building system. With Blade, users wrote a BUILD file and
 put it in each of the source directory.  In each BUILD file, there could be
 one or more build rules, each has a TARGET NAME, source files and dependent
 targets. Blade supports many types of build rules, such as:


    cc_binary         -- build an executable binary from C++ source
    cc_library        -- build a library from C++ source
    cc_plugin         -- build a plugin from C++ source
    cc_test           -- build a test program from C++ source
    cc_benchmark      -- build a benchmark binary from C++ source
    gen_rule          -- build targets with a specified general building rule
    java_library      -- build a java library from java source files
    java_binary       -- build a java executable from java source files
    java_test         -- build a java test program from java source files
    py_library        -- build a python library from python source files
    py_binary         -- build a python executable from python source files
    py_test           -- build a python test program from python source files
    lex_yacc_library  -- build a library from lex/yacc source
    proto_library     -- build a library from Protobuf source
    thrift_library    -- build a library from Thrift source
    fbthrift_library  -- build a library from Thrift source for Facebook's Thrift Cpp2
    resource_library  -- build resource library and gen header files
    swig_library      -- build swig extension module for python and java
    ...

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
                           <path> and its descendant directories.

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
from blade import target
from blade.blade_util import find_blade_root_dir, find_file_bottom_up
from blade.blade_util import get_cwd, iteritems, to_string
from blade.blade_util import lock_file, unlock_file

# Run target
_TARGETS = None

_BLADE_ROOT_DIR = None
_WORKING_DIR = None


# For our open source projects (toft, thirdparty, foxy etc.), we make a project
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
    for scm_root, (scm, dirs) in iteritems(scm_root_dirs):
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
        console.info('Cpplint is disabled')
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
    except KeyboardInterrupt as e:
        console.error(str(e))
        return 1
    return 0


def _run_backend_builder(cmdstr):
    console.debug('Run build command: ' + cmdstr)
    p = subprocess.Popen(cmdstr, shell=True)
    try:
        p.wait()
        return p.returncode
    # pylint: disable=bare-except
    except:  # KeyboardInterrupt
        return 1


def backend_builder_options(options):
    """Setup some options which are same in different backend builders."""
    build_options = []
    if options.dry_run:
        build_options.append('-n')
    if options.backend_builder_options:
        build_options.append(options.backend_builder_options)
    return build_options


def _show_slow_builds(build_start_time, show_builds_slower_than):
    build_dir = build_manager.instance.get_build_dir()
    with open(os.path.join(build_dir, '.ninja_log')) as f:
        head = f.readline()
        if '# ninja log v5' not in head:
            console.warning('Unknown ninja log version: %s' % head)
            return
        build_times = []
        for line in f.readlines():
            start_time, end_time, timestamp, target, cmdhash = line.split()
            cost_time = (int(end_time) - int(start_time)) / 1000.0  # ms -> s
            timestamp = int(timestamp)
            if timestamp >= build_start_time and cost_time > show_builds_slower_than:
                build_times.append((cost_time, target))
        if build_times:
            console.notice('Slow build targets:')
            for cost_time, target in sorted(build_times):
                console.notice('%.4gs\t%s' % (cost_time, target), prefix=False)


def _show_progress(p, rf):
    # Convert description message such as '[1/123] CC xxx.cc' into progress bar
    progress_re = re.compile(r'^\[(\d+)/(\d+)\]\s+')
    try:
        while True:
            p.poll()
            line = rf.readline().strip()
            if line:
                m = progress_re.match(line)
                if m:
                    console.show_progress_bar(int(m.group(1)), int(m.group(2)))
                else:
                    console.clear_progress_bar()
                    console.output(line)
            elif p.returncode is not None:
                break
            else:
                # Avoid cost too much cpu
                time.sleep(0.1)
    finally:
        console.clear_progress_bar()


def _run_ninja(cmd, options):
    cmdstr = subprocess.list2cmdline(cmd)
    if console.verbosity_compare(options.verbosity, 'quiet') > 0:
        return _run_backend_builder(cmdstr)
    ninja_output = 'blade-bin/ninja_output.log'
    with open(ninja_output, 'w', buffering=1) as wf, open(ninja_output, 'r', buffering=1) as rf:
        os.environ['NINJA_STATUS'] = '[%f/%t] '  # The progress depends on this format
        p = subprocess.Popen(cmdstr, shell=True, stdout=wf, stderr=subprocess.STDOUT)
        _show_progress(p, rf)
    return p.returncode


def _ninja_build(options):
    cmd = ['ninja', '-f', build_manager.instance.build_script()]
    cmd += backend_builder_options(options)
    cmd.append('-j%s' % build_manager.instance.build_jobs_num())
    if options.keep_going:
        cmd.append('-k0')
    if console.verbosity_compare(options.verbosity, 'verbose') >= 0:
        cmd.append('-v')
    build_start_time = time.time()
    ret = _run_ninja(cmd, options)
    if options.show_builds_slower_than is not None:
        _show_slow_builds(build_start_time, options.show_builds_slower_than)
    return ret


def build(options):
    _check_code_style(_TARGETS)
    console.info('Building...')
    console.flush()
    returncode = _ninja_build(options)
    if not build_manager.instance.verify():
        if returncode == 0:
            returncode = 1
    if returncode != 0:
        console.error('Build failure.')
        return returncode
    console.info('Build success.')
    return 0


def run(options):
    ret = build(options)
    if ret != 0:
        return ret
    run_target = _TARGETS[0]
    return build_manager.instance.run(run_target)


def test(options):
    if not options.no_build:
        ret = build(options)
        if ret != 0:
            return ret
    return build_manager.instance.test()


def clean(options):
    console.info('Cleaning...(hint: You can specify --generate-dynamic to '
                 'clean shared libraries)')
    backend_builder = config.get_item('global_config', 'backend_builder')
    cmd = [backend_builder]
    # cmd += backend_builder_options(options)
    cmd.append('-f%s' % build_manager.instance.build_script())
    cmd += ['-t', 'clean']
    cmdstr = subprocess.list2cmdline(cmd)
    returncode = _run_backend_builder(cmdstr)
    console.info('Cleaning done.')
    return returncode


def query(options):
    return build_manager.instance.query()


def dump(options):
    output_file_name = os.path.join(_WORKING_DIR, options.dump_to_file)
    if options.dump_compdb:
        _dump_compdb(options, output_file_name)
    elif options.dump_targets:
        build_manager.instance.dump_targets(output_file_name)


def _dump_compdb(options, output_file_name):
    backend_builder = config.get_item('global_config', 'backend_builder')
    if backend_builder != 'ninja':
        console.error_exit('Dump compdb only work when backend_builder is ninja')
    rules = build_manager.instance.get_all_rule_names()
    cmd = ['ninja', '-f', build_manager.instance.build_script(), '-t', 'compdb']
    cmd += rules
    cmdstr = subprocess.list2cmdline(cmd)
    cmdstr += ' > '
    cmdstr += output_file_name
    return _run_backend_builder(cmdstr)


def lock_workspace(build_dir):
    _BUILDING_LOCK_FILE ='.blade.building.lock'
    lock_file_fd, ret_code = lock_file(os.path.join(build_dir, _BUILDING_LOCK_FILE))
    if lock_file_fd == -1:
        if ret_code == errno.EAGAIN:
            console.error_exit('There is already an active building in current workspace.')
        else:
            console.error_exit('Lock exception, please try it later.')
    return lock_file_fd


def unlock_workspace(lock_file_fd):
    unlock_file(lock_file_fd)


def load_config(options, blade_root_dir):
    """load the configuration file and parse. """
    # Init global build attributes
    build_attributes.initialize(options)
    config.load_files(blade_root_dir, options.load_local_config)


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
    '''Get workspace dir and working dir relative to workspace dir'''
    working_dir = get_cwd()
    blade_root_dir = find_blade_root_dir(working_dir)
    working_dir = os.path.relpath(working_dir, blade_root_dir)

    return blade_root_dir, working_dir


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
    common_options = ('debug_info_level', 'backend_builder', 'build_jobs', 'test_jobs')
    for name in common_options:
        value = getattr(options, name, None)
        if value:
            config.global_config(**{name: value})


def clear_build_script():
    scripts = [build_manager.instance.build_script()]
    for script in scripts:
        script = os.path.join(_BLADE_ROOT_DIR, script)
        try:
            os.remove(script)
        except OSError:
            pass


def run_subcommand(command, options, targets, blade_path, build_dir):
    """Run particular commands before loading"""
    # The 'dump' command is special, some kind of dump items should be ran before loading.
    if command == 'dump' and options.dump_config:
        output_file_name = os.path.join(_WORKING_DIR, options.dump_to_file)
        config.dump(output_file_name)
        return 0

    load_targets = targets
    if command == 'query' and options.dependents:
        # In query dependents mode, we must load all targets in workspace to get a whole view
        load_targets = ['.:...']
    build_manager.initialize(targets,
                             load_targets,
                             blade_path,
                             _WORKING_DIR,
                             build_dir,
                             _BLADE_ROOT_DIR,
                             options,
                             command)

    # Build the targets
    build_manager.instance.load_targets()
    if options.stop_after == 'load':
        return 0
    build_manager.instance.analyze_targets()
    if options.stop_after == 'analyze':
        return 0
    build_manager.instance.generate()
    if options.stop_after == 'generate':
        return 0

    # Switch case due to different sub command
    action = {
        'build': build,
        'clean': clean,
        'dump': dump,
        'query': query,
        'run': run,
        'test': test,
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
    console.output('Binary profile file `%s` is also generated, '
                   'you can use `gprof2dot` or `vprof` to convert it to graph, eg:' % pstats_file)
    console.output('  gprof2dot.py -f pstats --color-nodes-by-selftime %s'
                   ' | dot -T pdf -o blade.pdf' % pstats_file)
    return exit_code[0]


def _main(blade_path, argv):
    """The main entry of blade. """
    command, options, targets = command_line.parse(argv)
    setup_console(options)

    global _BLADE_ROOT_DIR
    global _WORKING_DIR
    _BLADE_ROOT_DIR, _WORKING_DIR = get_source_dirs()
    if _BLADE_ROOT_DIR != _WORKING_DIR:
        # This message is required by vim quickfix mode if pwd is changed during
        # the building, DO NOT change the pattern of this message.
        if options.verbosity != 'quiet':
            print("Blade: Entering directory `%s'" % _BLADE_ROOT_DIR)
        os.chdir(_BLADE_ROOT_DIR)

    load_config(options, _BLADE_ROOT_DIR)
    adjust_config_by_options(config, options)

    global _TARGETS
    if not targets:
        targets = ['.']
    targets = target.normalize(targets, _WORKING_DIR)
    _TARGETS = targets

    build_dir = setup_build_dir(options)
    setup_log(build_dir, options)

    generate_scm(build_dir)

    lock_file_fd = lock_workspace(build_dir)
    try:
        if options.profiling:
            return run_subcommand_profile(command, options, targets, blade_path, build_dir)
        return run_subcommand(command, options, targets, blade_path, build_dir)
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
        exit_code = e.code  # pylint: disable=redefined-variable-type
    except KeyboardInterrupt:
        console.error('KeyboardInterrupt')
        exit_code = -signal.SIGINT
    except:  # pylint: disable=bare-except
        exit_code = 1
        console.error(traceback.format_exc())
    if exit_code != 0:
        console.error('Failure')
    return exit_code
