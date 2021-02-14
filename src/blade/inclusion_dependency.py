# Copyright (c) 2021 Tencent Inc.
# All rights reserved.
#
# Author: chen3feng <chen3feng@gmail.com>
# Date:   Feb 14, 2013

"""C/C++ header file inclusion dependency declaration and check."""

import collections
import os

from blade import config
from blade import console
from blade import util


# A dict[hdr, set(target)]
# For a header file, which targets declared it.
_hdr_targets_map = collections.defaultdict(set)

# A dict[inc, set(target)]
# For a include dir, which targets declared it.
_hdr_dir_targets_map = collections.defaultdict(set)


def declare_hdrs(target, hdrs):
    """Declare hdr to lib relationships

    Args:
        target: the target which owns the hdrs
        hdrs:list, the full path (based in workspace troot) of hdrs
    """
    for hdr in hdrs:
        assert not hdr.startswith(target.build_dir)
        hdr = target._source_file_path(hdr)
        _hdr_targets_map[hdr].add(target.key)


def declare_hdr_dir(target, inc):
    """Declare a inc:lib relationship

    Args:
        target: the target which owns the include dir
        inc:str, the full path (based in workspace troot) of include dir
    """
    assert not inc.startswith(target.build_dir), inc
    inc = target._source_file_path(inc)
    _hdr_dir_targets_map[inc].add(target.key)


def _find_libs_by_header(hdr):
    libs = _hdr_targets_map.get(hdr)
    if libs:
        return libs
    hdr_dir = os.path.dirname(hdr)
    while True:
        libs = _hdr_dir_targets_map.get(hdr_dir)
        if libs:
            return libs
        old_hdr_dir = hdr_dir
        hdr_dir = os.path.dirname(hdr_dir)
        if hdr_dir == old_hdr_dir:
            return set()


# dict(hdr, set(targets))
_private_hdrs_target_map = collections.defaultdict(set)


def declare_private_hdrs(target, hdrs):
    """Declare private header files of a cc target."""
    for h in hdrs:
        hdr = target._source_file_path(h)
        _private_hdrs_target_map[hdr].add(target.key)


def _find_targets_by_private_hdr(hdr):
    """Find targets by private header file."""
    return _private_hdrs_target_map[hdr]


def _parse_hdr_level_line(line):
    """Parse a normal line of a header stack file

    Example:
        . ./common/rpc/rpc_client.h
    """
    pos = line.find(' ')
    if pos == -1:
        return -1, ''
    level, hdr = line[:pos].count('.'), line[pos + 1:]
    if hdr.startswith('./'):
        hdr = hdr[2:]
    return level, hdr


def _find_inclusion_file(target, src, is_header):
    """Find the '.H' file for the given src.

    The `.H` file is generated from gcc's `-H` option, see
    https://gcc.gnu.org/onlinedocs/gcc/Preprocessor-Options.html
    for details.
    """
    # NOTE: The inclusion file for header file and impl file has different extension name.
    objs_dir = target._target_file_path(target.name + '.objs')
    path = ('%s.H' if is_header else '%s.o.H') % os.path.join(objs_dir, src)
    if not os.path.exists(path):
        return ''
    return path


def _parse_inclusion_stacks(path, build_dir):
    """Parae headers inclusion stacks from file.

    Given the following inclusions found in the app/example/foo.cc.o.H:

        . ./app/example/foo.h
        .. build64_release/app/example/proto/foo.pb.h
        ... build64_release/common/rpc/rpc_service.pb.h
        . build64_release/app/example/proto/bar.pb.h
        . ./common/rpc/rpc_client.h
        .. build64_release/common/rpc/rpc_options.pb.h

    Return a list of all directly included header files and a list with each item being a list
    representing where the header
    is included from in the current translation unit.

    Note that we will STOP tracking at the first generated header (if any)
    while other headers included from the header directly or indirectly are
    ignored since that part of dependency is ensured by the generator, such
    as proto_library.

    As shown in the example above, it returns the following directly header list:

        [
            'app/example/foo.h',
            'build64_release/app/example/proto/bar.pb.h',
            'common/rpc/rpc_client.h',
        ]

    and the inclusion stacks:

        [
            ['app/example/foo.h', 'build64_release/app/example/proto/foo.pb.h'],
            ['build64_release/app/example/proto/bar.pb.h'],
            ['common/rpc/rpc_client.h', 'build64_release/common/rpc/rpc_options.pb.h'],
        ]
    """
    direct_hdrs = []  # The directly included header files
    stacks, hdrs_stack = [], []

    def _process_hdr(level, hdr, current_level):
        if hdr.startswith('/'):
            skip_level = level
        elif hdr.startswith(build_dir):
            skip_level = level
            stacks.append(hdrs_stack + [_remove_build_dir_prefix(hdr, build_dir)])
        else:
            current_level = level
            hdrs_stack.append(_remove_build_dir_prefix(hdr, build_dir))
            skip_level = -1
        return current_level, skip_level

    current_level = 0
    skip_level = -1
    with open(path) as f:
        for line in f:
            line = line.rstrip()  # Strip `\n`
            if not line.startswith('.'):
                # The remaining lines are useless for us
                break
            level, hdr = _parse_hdr_level_line(line)
            if level == -1:
                console.log('%s: Unrecognized line %s' % (path, line))
                break
            if level == 1 and not hdr.startswith('/'):
                direct_hdrs.append(_remove_build_dir_prefix(hdr, build_dir))
            if level > current_level:
                if skip_level != -1 and level > skip_level:
                    continue
                assert level == current_level + 1
                current_level, skip_level = _process_hdr(level, hdr, current_level)
            else:
                while current_level >= level:
                    current_level -= 1
                    hdrs_stack.pop()
                current_level, skip_level = _process_hdr(level, hdr, current_level)

    return direct_hdrs, stacks


def _remove_build_dir_prefix(path, build_dir):
    """Remove the build dir prefix of path (e.g. build64_release/)
    Args:
        path:str, the full path starts from the workspace root
    """
    prefix = build_dir + os.sep
    if path.startswith(prefix):
        return path[len(prefix):]
    return path


def _hdr_is_declared(hdr, declared_hdrs, declared_incs):
    if hdr in declared_hdrs:
        return True
    for dir in declared_incs:
        if hdr.startswith(dir):
            return True
    return False


def _verify_direct_headers(target, src, direct_hdrs, suppressd_hdrs,
                           undeclared_hdrs, missing_dep_hdrs, verify_msg):
    """
    Verify directly included header files is in deps.

    Returns:
        whether it is correct, regardless of whether it is suppressed.
    """
    allowed_undeclared_hdrs = config.get_item('cc_config', 'allowed_undeclared_hdrs')
    ok = True
    msg = []
    for hdr in direct_hdrs:
        libs = _find_libs_by_header(hdr)
        if not libs:
            ok = False
            libs = _find_targets_by_private_hdr(hdr)
            if libs:
                if target.key not in libs:
                    msg.append('    "%s" is a private header file of %s' % (
                        hdr, _or_joined_libs(libs)))
                continue
            if hdr not in allowed_undeclared_hdrs:
                msg.append('    %s' % _header_undeclared_message(target, hdr))
            undeclared_hdrs.add(hdr)
            continue
        deps = set(target.deps + [target.key])  # Don't forget target itself
        if not (libs & deps):  # pylint: disable=superfluous-parens
            ok = False
            # NOTE:
            # We just don't report a suppressd hdr, but still need to record it as a failure.
            # Because a passed src will not be verified again, even if we remove it from the
            # suppress list.
            # Same reason in the _verify_generated_headers.
            missing_dep_hdrs.add(hdr)
            if hdr not in suppressd_hdrs:
                msg.append('    For %s' % _hdr_declaration_message(hdr, libs))
    if msg:
        verify_msg.append('  In file included from "%s",' % src)
        verify_msg += msg
    return ok


def _header_undeclared_message(target, hdr):
    msg = '"%s" is not declared in any cc target. ' % hdr
    if util.path_under_dir(hdr, target.path):
        msg += 'If it belongs to this target, it should be declared in "src"'
        if target.type.endswith('_library'):
            msg += ' if it is private or in "hdrs" if it is public'
        msg += ', otherwise '
    msg += 'it should be declared in "hdrs" of the appropriate library to which it belongs'
    return msg


def _hdr_declaration_message(hdr, libs=None):
    if libs is None:
        libs = _find_libs_by_header(hdr)
    if not libs:
        return hdr
    return '"%s", which belongs to %s' % (hdr, _or_joined_libs(libs))


def _or_joined_libs(libs):
    """Return " or " joind libs descriptive string."""
    return ' or '.join(['"//%s"' % lib for lib in libs])


def _verify_generated_headers(target, src, stacks, declared_hdrs, declared_incs,
                              suppressd_hdrs, direct_hdrs, missing_dep_hdrs, verify_msg):
    """
    Verify indirectly included generated header files is in deps.

    Returns:
        whether it is correct, regardless of whether it is suppressed.
    """
    ok = True
    msg = []
    for stack in stacks:
        generated_hdr = stack[-1]
        if generated_hdr in direct_hdrs:  # Already verified as direct_hdrs
            continue
        if _hdr_is_declared(generated_hdr, declared_hdrs, declared_incs):
            continue
        ok = False
        stack.pop()
        missing_dep_hdrs.add(generated_hdr)
        if generated_hdr in suppressd_hdrs:
            continue
        source = target._source_file_path(src)
        msg.append('  For "%s"' % _hdr_declaration_message(generated_hdr))
        if not stack:
            msg.append('    In file included from "%s"' % source)
        else:
            stack.reverse()
            msg.append('    In file included from %s' % _hdr_declaration_message(stack[0]))
            prefix = '                     from "%s"'
            msg += [prefix % _hdr_declaration_message(h) for h in stack[1:]]
            msg.append(prefix % source)
    verify_msg += msg
    return ok


def _collect_declared_generated_includes(target):
    """Collect header/include declarations."""
    declared_hdrs = set()
    declared_incs = set()

    build_targets = target.blade.get_build_targets()
    for key in target.expanded_deps:
        dep = build_targets[key]
        for hdr in dep.attr.get('generated_hdrs', []):
            declared_hdrs.add(_remove_build_dir_prefix(hdr, target.build_dir))
        for inc in dep.attr.get('generated_incs', []):
            declared_incs.add(_remove_build_dir_prefix(inc, target.build_dir))
    return declared_hdrs, declared_incs


def check(target, history, suppress):
    """
    Verify whether included header files is declared in "deps" correctly.

    Returns:
        Whether nothing is wrong.
    """
    declared_hdrs, declared_incs = _collect_declared_generated_includes(target)
    # Verify
    details = {}  # {src: list(hdrs)}
    undeclared_hdrs = set()
    preprocess_paths, failed_preprocess_paths = set(), set()

    direct_verify_msg = []
    generated_verify_msg = []

    def verify_file(src, is_header):
        path = _find_inclusion_file(target, src, is_header)
        if not path or (path in history and int(os.path.getmtime(path)) == history[path]):
            return

        direct_hdrs, stacks = _parse_inclusion_stacks(path, target.build_dir)
        preprocess_paths.add(path)
        missing_dep_hdrs = set()
        if not _verify_direct_headers(
                target, src, direct_hdrs, suppress.get(src, []),
                undeclared_hdrs, missing_dep_hdrs, direct_verify_msg):
            failed_preprocess_paths.add(path)

        # But direct headers can not cover all, so it is still useful
        if not _verify_generated_headers(
                target, src, stacks, declared_hdrs, declared_incs, suppress.get(src, []), direct_hdrs,
                missing_dep_hdrs, generated_verify_msg):
            failed_preprocess_paths.add(path)

        if missing_dep_hdrs:
            details[src] = list(missing_dep_hdrs)

    for src in target.srcs:
        verify_file(src, is_header=False)

    for hdr, full_hdr in target.attr['expanded_hdrs']:
        verify_file(hdr, is_header=True)

    severity = config.get_item('cc_config', 'hdr_dep_missing_severity')
    output = getattr(target, severity)
    if direct_verify_msg:
        output('Missing dependency declaration:\n%s' % '\n'.join(direct_verify_msg))
    if generated_verify_msg:
        output('Missing indirect dependency declaration:\n%s' % '\n'.join(generated_verify_msg))

    # Update history
    for preprocess in failed_preprocess_paths:
        if preprocess in history:
            del history[preprocess]
    for preprocess in preprocess_paths - failed_preprocess_paths:
        history[preprocess] = int(os.path.getmtime(preprocess))

    ok = not direct_verify_msg and not generated_verify_msg or severity != 'error'

    return ok, details, undeclared_hdrs
