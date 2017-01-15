# Copyright (c) 2011 Tencent Inc.
# All rights reserved.
#
# Author: Huan Yu <huanyu@tencent.com>
#         Feng Chen <phongchen@tencent.com>
#         Yi Wang <yiwang@tencent.com>
#         Chong Peng <michaelpeng@tencent.com>
# Date:   October 20, 2011


"""
 This is the dependencies expander module which accepts the targets loaded
 from BUILD files and will find all of the targets needed by the target and
 add extra options according to different target types.

"""


import console


"""
Given the map of related targets, i.e., the subset of target_database
that are dependencies of those targets speicifed in Blade command
line, this utility class expands the 'deps' property of each target
to be all direct and indirect dependencies of that target.

After expanded the dependencies of targets, sort the topologically
and then provide the query interface to users by blade manager.

"""


def analyze_deps(related_targets):
    """analyze the dependency relationship between targets.

    Input: related targets after loading targets from BUILD files.
           {(target_path, target_name) : (target_data), ...}

    Output:
        1. the targets that are expanded
            {(target_path, target_name) : (target_data with deps expanded), ...}
        2. the keys sorted
            [all the targets keys] - sorted
        3. the targets successors dict which is the transpose of #1
            {(target_path, target_name) : [the depended target keys]}

    """
    _expand_deps(related_targets)
    return _topological_sort(related_targets)


def _expand_deps(targets):
    """_expand_deps.

    Find out all the targets that certain target depeneds on them.
    Fill the related options according to different targets.

    """
    deps_map_cache = {}  # Cache expanded target deps to avoid redundant expand
    for target_id in targets:
        target = targets[target_id]
        target.expanded_deps = _find_all_deps(target_id, targets, deps_map_cache)
        # Handle the special case: dependencies of a dynamic_cc_binary
        # must be built as dynamic libraries.
        # TODO(phongchen): Refactor with abstract method expand_deps
        if target.data.get('dynamic_link'):
            for dep in target.expanded_deps:
                targets[dep].data['build_dynamic'] = True
        elif target.type == 'swig_library':
            for dep in target.expanded_deps:
                if targets[dep].type == 'proto_library':
                    targets[dep].data['generate_php'] = True
        elif target.type == 'py_binary' or target.type == 'py_library' or target.type == 'py_egg':
            for dep in target.expanded_deps:
                targets[dep].data['generate_python'] = True
        elif target.type.startswith('java_'):
            for dep in target.expanded_deps:
                targets[dep].data['generate_java'] = True
        elif target.type.startswith('scala_'):
            for dep in target.expanded_deps:
                targets[dep].data['generate_scala'] = True
        elif target.type.startswith('go_'):
            for dep in target.expanded_deps:
                targets[dep].data['generate_go'] = True


def _check_dep_visibility(target, dep, targets):
    """Check whether target is able to depend on dep. """
    if dep not in targets:
        console.error_exit('Target %s:%s depends on %s:%s, '
                           'but it is missing, exit...' % (
                           target_id[0], target_id[1], dep[0], dep[1]))
    # Targets are visible inside the same BUILD file by default
    if target[0] == dep[0]:
        return

    d = targets[dep]
    visibility = getattr(d, 'visibility', 'PUBLIC')
    if visibility == 'PUBLIC':
        return
    if target not in visibility:
        console.error_exit('%s:%s is not allowed to depend on %s '
                           'because of visibility.' % (
                           target[0], target[1], d.fullname))


def _find_all_deps(target_id, targets, deps_map_cache, root_targets=None):
    """_find_all_deps.

    Return all targets depended by target_id directly and/or indirectly.
    We need the parameter root_target_id to check loopy dependency.

    """
    new_deps_list = deps_map_cache.get(target_id)
    if new_deps_list is not None:
        return new_deps_list

    if root_targets is None:
        root_targets = set()

    root_targets.add(target_id)
    new_deps_list = []

    for d in targets[target_id].expanded_deps:
        # loop dependency
        if d in root_targets:
            err_msg = ''
            for t in root_targets:
                err_msg += '//%s:%s --> ' % (t[0], t[1])
            console.error_exit('loop dependency found: //%s:%s --> [%s]' % (
                       d[0], d[1], err_msg))
        _check_dep_visibility(target_id, d, targets)
        new_deps_piece = [d]
        new_deps_piece += _find_all_deps(d, targets, deps_map_cache, root_targets)
        # Append new_deps_piece to new_deps_list, be aware of de-duplication
        for nd in new_deps_piece:
            if nd in new_deps_list:
                new_deps_list.remove(nd)
            new_deps_list.append(nd)

    deps_map_cache[target_id] = new_deps_list
    root_targets.remove(target_id)

    return new_deps_list


def _topological_sort(pairlist):
    """Sort the targets. """
    numpreds = {}    # elt -> # of predecessors
    successors = {}  # elt -> list of successors
    for second, target in pairlist.items():
        if second not in numpreds:
            numpreds[second] = 0
        if second not in successors:
            successors[second] = []
        deps = target.expanded_deps
        for first in deps:
            # make sure every elt is a key in numpreds
            if first not in numpreds:
                numpreds[first] = 0

            # since first < second, second gains a pred ...
            numpreds[second] = numpreds[second] + 1

            # ... and first gains a succ
            if first in successors:
                successors[first].append(second)
            else:
                successors[first] = [second]

    # suck up everything without a predecessor
    answer = filter(lambda x, numpreds=numpreds: numpreds[x] == 0,
                    numpreds.keys())

    # for everything in answer, knock down the pred count on
    # its successors; note that answer grows *in* the loop
    for x in answer:
        assert numpreds[x] == 0
        del numpreds[x]
        if x in successors:
            for y in successors[x]:
                numpreds[y] = numpreds[y] - 1
                if numpreds[y] == 0:
                    answer.append(y)

    return answer, successors
