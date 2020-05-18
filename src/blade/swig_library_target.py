# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define swig_library target
"""

from __future__ import absolute_import

import os

from blade import build_manager
from blade import build_rules
from blade import console
from blade.cc_targets import CcTarget


class SwigLibrary(CcTarget):
    """This class is used to build swig library."""

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 java_package,
                 java_lib_packed,
                 optimize,
                 extra_swigflags,
                 blade,
                 kwargs):
        CcTarget.__init__(self,
                          name,
                          'swig_library',
                          srcs,
                          deps,
                          None,
                          warning,
                          [], [], [], optimize, extra_swigflags, [],
                          blade,
                          kwargs)
        self.data['cpperraswarn'] = warning
        self.data['java_package'] = java_package
        self.data['java_lib_packed'] = java_lib_packed
        self.data['java_dep_var'] = []
        self.data['java_sources_explict_dependency'] = []
        self.data['python_vars'] = []
        self.data['python_sources'] = []

        build_platform = self.blade.get_build_platform()
        self.php_inc_list = build_platform.get_php_include()
        self.options = self.blade.get_options()

    def _expand_deps_generation(self):
        build_targets = self.blade.get_build_targets()
        for dep in self.expanded_deps:
            d = build_targets[dep]
            if d.type == 'proto_library':
                d.data['generate_php'] = True

    def _pyswig_gen_python_file(self, path, src):
        """Generate swig python file for python. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s.py' % swig_name)

    def _pyswig_gen_file(self, path, src):
        """Generate swig cxx files for python. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s_pywrap.cxx' % swig_name)

    def _javaswig_gen_file(self, path, src):
        """Generate swig cxx files for java. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s_javawrap.cxx' % swig_name)

    def _phpswig_gen_file(self, path, src):
        """Generate swig cxx files for php. """
        swig_name = src[:-2]
        return os.path.join(self.build_path, path, '%s_phpwrap.cxx' % swig_name)

    def _swig_extract_dependency_files(self, src):
        dep = []
        for line in open(src):
            if line.startswith('#include') or line.startswith('%include'):
                line = line.split(' ')[1].strip("""'"\r\n""")
                if not ('<' in line or line in dep):
                    dep.append(line)
        return [i for i in dep if os.path.exists(i)]

    def ninja_rules(self):
        self.error('not implemented')


def swig_library(name,
                 srcs=[],
                 deps=[],
                 warning='',
                 java_package='',
                 java_lib_packed=False,
                 optimize=[],
                 extra_swigflags=[],
                 **kwargs):
    """swig_library target. """
    target = SwigLibrary(name,
                         srcs,
                         deps,
                         warning,
                         java_package,
                         java_lib_packed,
                         optimize,
                         extra_swigflags,
                         build_manager.instance,
                         kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(swig_library)
