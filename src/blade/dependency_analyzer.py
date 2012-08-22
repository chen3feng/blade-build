"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Huan Yu <huanyu@tencent.com>
         Feng chen <phongchen@tencent.com>
         Yi Wang <yiwang@tencent.com>
         Chong peng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the dependencies expander module which accepts the targets loaded
 from BUILD files and will find all of the targets needed by the target and
 add extra options according to different target types.

"""


from blade_util import error_exit


class DependenciesAnalyzer(object):
    """DependenciesAnalyzer.

    Given the map of related targets, i.e., the subset of target_database
    that are dependencies of those targets speicifed in Blade command
    line, this utility class expands the 'deps' property of each target
    to be all direct and indirect dependencies of that target.

    After expanded the dependencies of targets, sort the topologically
    and then provide the query interface to users by blade manager.

    """
    def __init__(self, blade):
        """Init the dependency expander. """
        self.targets = dict(blade.get_related_targets())
        self.blade = blade
        self.deps_map_cache = {}

    def analyze_deps(self):
        """analyze the dependency relationship between targets.

        Input: related targets after loading targets from BUILD files.
               {(target_path, target_name) : (target_data), ...}

        Output:the targets that are expanded and the keys sorted
               [all the targets keys] - sorted
               {(target_path, target_name) : (target_data with deps expanded), ...}

        """
        # Expanded the dependency at first
        self._expand_deps()
        # Status : self.targets expanded

        keys_list_sorted = self._topological_sort(self.targets)
        # Status : self.targets keys sorted

        self.blade.set_sorted_targets_keys(keys_list_sorted)
        # Done : it could provide the query inetrface
        # to users now (from blade or blade manager)

    def _expand_deps(self):
        """_expand_deps.

        Find out all the targets that certain target depeneds on them.
        Fill the related options according to different targets.

        """
        for target_id in self.targets.keys():
            self.targets[target_id]['deps'] = self._find_all_deps(target_id)
            # Handle the special case: dependencies of a dynamic_cc_binary
            # must be built as dynamic libraries.
            if (self.targets[target_id]['type'] == 'dynamic_cc_binary') or (
                self.targets[target_id]['type'] == 'dynamic_cc_test'):
                for dep in self.targets[target_id]['deps']:
                    self.targets[dep]['options']['build_dynamic'] = True
            elif self.targets[target_id]['type'] == 'swig_library':
                for dep in self.targets[target_id]['deps']:
                    if self.targets[dep]['type'] == 'proto_library':
                        self.targets[dep]['options']['generate_php'] = True
            elif self.targets[target_id]['type'] == 'py_binary':
                for dep in self.targets[target_id]['deps']:
                    if self.targets[dep]['type'] == 'proto_library':
                        self.targets[dep]['options']['generate_python'] = True
            elif self.targets[target_id]['type'] == 'java_jar':
                for dep in self.targets[target_id]['deps']:
                    if self.targets[dep]['type'] == 'proto_library':
                        self.targets[dep]['options']['generate_java'] = True
                    elif self.targets[dep]['type'] == 'swig_library':
                        self.targets[dep]['options']['generate_java'] = True

        self.blade.set_all_targets_expanded(self.targets)

    def _find_all_deps(self, target_id, root_target_id=None):
        """_find_all_deps.

        Return all targets depended by target_id directly and/or indirectly.
        We need the parameter root_target_id to check loopy dependency.

        """
        if root_target_id == None:
            root_target_id = target_id

        new_deps_list = self.deps_map_cache.get(target_id, [])
        if new_deps_list:
            return new_deps_list

        for d in self.targets[target_id]['deps']:
            if d == root_target_id:
                print "loop dependency of %s" % ':'.join(root_target_id)
            new_deps_piece = [d]
            if d not in self.targets:
                error_exit('Target %s:%s depends on %s:%s, '
                            'but it is missing, exit...' % (target_id[0],
                                                            target_id[1],
                                                            d[0],
                                                            d[1]))
            new_deps_piece += self._find_all_deps(d, root_target_id)
            # Append new_deps_piece to new_deps_list, be aware of
            # de-duplication:
            for nd in new_deps_piece:
                if nd in new_deps_list:
                    new_deps_list.remove(nd)
                new_deps_list.append(nd)
        self.deps_map_cache[target_id] = new_deps_list
        return new_deps_list

    def _topological_sort(self, pairlist):
        """Sort the targets. """
        numpreds = {}   # elt -> # of predecessors
        successors = {} # elt -> list of successors
        for second, options in pairlist.items():
            if not numpreds.has_key(second):
                numpreds[second] = 0
            deps = options['deps']
            for first in deps:
                # make sure every elt is a key in numpreds
                if not numpreds.has_key(first):
                    numpreds[first] = 0

                # since first < second, second gains a pred ...
                numpreds[second] = numpreds[second] + 1

                # ... and first gains a succ
                if successors.has_key(first):
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
            if successors.has_key(x):
                for y in successors[x]:
                    numpreds[y] = numpreds[y] - 1
                    if numpreds[y] == 0:
                        answer.append(y)

        return answer
