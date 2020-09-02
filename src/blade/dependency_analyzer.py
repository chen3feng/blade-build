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
from __future__ import absolute_import

from collections import deque

from blade import console


def analyze_deps(related_targets):
    """
    Analyze the dependency relationship between targets.

    Given the map of related targets, i.e., the subset of target_database
    that are dependencies of those targets speicifed in Blade command
    line, this utility class expands the 'deps' property of each target
    to be all direct and indirect dependencies of that target.

    After expanded the dependencies of targets, sort the topologically
    and then provide the query interface to users by blade manager.

    Input: related targets after loading targets from BUILD files.
           {target_key : (target_data), ...}

    Output:
        1. the targets that are expanded
            {target_key : (target_data with deps expanded), ...}
        2. the keys sorted
            [all the targets keys] - sorted
        3. the targets dependents_map dict which is the transpose of #1
            {target_key : [the depended target keys]}
    """
    _expand_deps(related_targets)
    return _topological_sort(related_targets)


def _expand_deps(targets):
    """_expand_deps.

    Find out all the targets that certain target depeneds on them.
    Fill the related options according to different targets.

    """
    for target_id in targets:
        target = targets[target_id]
        _expand_target_deps(target_id, targets)
        target._expand_deps_generation()


def _check_dep_visibility(target_id, dep_id, targets):
    """Check whether target is able to depend on dep. """
    target = targets[target_id]

    # Targets are visible inside the same BUILD file by default
    target_dir = target_id.rsplit(':')[0]
    dep_dir = dep_id.rsplit(':')[0]
    if target_dir == dep_dir:
        return

    dep = targets[dep_id]
    visibility = getattr(dep, 'visibility', 'PUBLIC')
    if visibility == 'PUBLIC':
        return
    if target_id not in visibility:
        target.error('Not allowed to depend on //%s because of visibility,' % dep_id)
        dep.info('which is declared here')


def _unique_deps(new_deps_list):
    # Append new_deps_piece to new_deps_list, be aware of de-duplication
    result = []
    deps = set()
    for dep in reversed(new_deps_list):
        if dep not in deps:
            result.append(dep)
            deps.add(dep)
    return list(reversed(result))


def _expand_target_deps(target_id, targets, root_targets=None):
    """_expand_target_deps.

    Return all targets depended by target_id directly and/or indirectly.
    We need the parameter root_target_id to check loopy dependency.

    """
    target = targets[target_id]
    if target.expanded_deps is not None:
        return target.expanded_deps

    if root_targets is None:
        root_targets = set()

    root_targets.add(target_id)
    new_deps_list = []

    for d in target.deps:
        # loop dependency
        if d in root_targets:
            err_msg = ''
            for t in root_targets:
                err_msg += '//%s --> ' % t
            console.fatal('Loop dependency found: //%s --> [%s]' % (d, err_msg))
        _check_dep_visibility(target_id, d, targets)
        new_deps_list.append(d)
        new_deps_list += _expand_target_deps(d, targets, root_targets)

    new_deps_list = _unique_deps(new_deps_list)
    target.expanded_deps = new_deps_list
    root_targets.remove(target_id)

    return new_deps_list


def _topological_sort(related_targets):
    """Sort the targets.
    Args:
        related_targets: dict{target_key, target} to be built
    Returns:
        sorted_target_key, keys sorted according to dependency relationship
        dependents_map, dict{target_key, target's dependents}
    """
    numpreds = {}  # elt -> # of predecessors
    dependents_map = {}  # elt -> list of dependents
    for target_key, target in related_targets.items():
        if target_key not in numpreds:
            numpreds[target_key] = 0
        if target_key not in dependents_map:
            dependents_map[target_key] = []
        for depkey in target.expanded_deps:
            # make sure every elt is a key in numpreds
            if depkey not in numpreds:
                numpreds[depkey] = 0

            # since depkey < target_key, target_key gains a pred ...
            numpreds[target_key] = numpreds[target_key] + 1

            # ... and depkey gains a succ
            if depkey in dependents_map:
                dependents_map[depkey].append(target_key)
            else:
                dependents_map[depkey] = [target_key]

    # suck up everything without a predecessor
    q = deque([key for key, num in numpreds.items() if num == 0])

    # for everything in queue, knock down the pred count on
    # its dependents_map
    sorted_target_keys = []
    while q:
        x = q.popleft()
        del numpreds[x]
        sorted_target_keys.append(x)
        if x in dependents_map:
            for y in dependents_map[x]:
                numpreds[y] -= 1
                if numpreds[y] == 0:
                    q.append(y)

    return sorted_target_keys, dependents_map
