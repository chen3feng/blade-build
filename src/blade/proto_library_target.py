# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define proto_library target
"""


import os
import re
import blade

import console
import configparse
import build_rules
import java_targets
from blade_util import var_to_list
from cc_targets import CcTarget


class ProtoLibrary(CcTarget, java_targets.JavaTargetMixIn):
    """A scons proto library target subclass.

    This class is derived from SconsCcTarget.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 optimize,
                 deprecated,
                 blade,
                 kwargs):
        """Init method.

        Init the proto target.

        """
        srcs_list = var_to_list(srcs)
        self._check_proto_srcs_name(srcs_list)
        CcTarget.__init__(self,
                          name,
                          'proto_library',
                          srcs,
                          deps,
                          '',
                          [], [], [], optimize, [], [],
                          blade,
                          kwargs)

        proto_config = configparse.blade_config.get_config('proto_library_config')
        protobuf_libs = var_to_list(proto_config['protobuf_libs'])
        protobuf_java_libs = var_to_list(proto_config['protobuf_java_libs'])

        # Hardcode deps rule to thirdparty protobuf lib.
        self._add_hardcode_library(protobuf_libs)

        # Link all the symbols by default
        self.data['link_all_symbols'] = True
        self.data['deprecated'] = deprecated
        self.data['java_sources_explict_dependency'] = []
        self.data['python_vars'] = []
        self.data['python_sources'] = []

    def _check_proto_srcs_name(self, srcs_list):
        """_check_proto_srcs_name.

        Checks whether the proto file's name ends with 'proto'.

        """
        err = 0
        for src in srcs_list:
            base_name = os.path.basename(src)
            pos = base_name.rfind('.')
            if pos == -1:
                err = 1
            file_suffix = base_name[pos + 1:]
            if file_suffix != 'proto':
                err = 1
            if err == 1:
                console.error_exit('invalid proto file name %s' % src)

    def _generate_header_files(self):
        """Whether this target generates header files during building."""
        return True

    def _proto_gen_files(self, src):
        """_proto_gen_files. """
        proto_name = src[:-6]
        return (self._target_file_path('%s.pb.cc' % proto_name),
                self._target_file_path('%s.pb.h' % proto_name))

    def _proto_gen_php_file(self, src):
        """Generate the php file name. """
        proto_name = src[:-6]
        return self._target_file_path('%s.pb.php' % proto_name)

    def _proto_gen_python_file(self, src):
        """Generate the python file name. """
        proto_name = src[:-6]
        return self._target_file_path('%s_pb2.py' % proto_name)

    def _get_java_package_name(self, content):
        """Get the java package name from proto file if it is specified. """
        java_package_pattern = '^\s*option\s*java_package\s*=\s*["\']([\w.]+)'
        m = re.search(java_package_pattern, content, re.MULTILINE)
        if m:
            return m.group(1)

        package_pattern = '^\s*package\s+([\w.]+)'
        m = re.search(package_pattern, content, re.MULTILINE)
        if m:
            return m.group(1)

        return ''

    def _proto_java_gen_class_name(self, src, content):
        """Get generated java class name"""
        pattern = '^\s*option\s+java_outer_classname\s*=\s*[\'"](\w+)["\']'
        text = open(self._source_file_path(src)).read()
        m = re.search(pattern, content, re.MULTILINE)
        if m:
            return m.group(1)
        proto_name = src[:-6]
        base_name = os.path.basename(proto_name)
        return ''.join(base_name.title().split('_'))

    def _proto_java_gen_file(self, src):
        """Generate the java files name of the proto library. """
        f = open(self._source_file_path(src))
        content = f.read()
        f.close()
        package_dir = self._get_java_package_name(content).replace('.', '/')
        class_name = self._proto_java_gen_class_name(src, content)
        java_name = '%s.java' % class_name
        return package_dir, java_name

    def _proto_java_rules(self):
        """Generate scons rules for the java files from proto file. """
        java_srcs = []
        java_src_vars = []
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            package_dir, java_name = self._proto_java_gen_file(src)
            proto_java_src = self._target_file_path(
                    os.path.join(os.path.dirname(src), package_dir, java_name))
            java_srcs.append(proto_java_src)
            java_src_var = self._var_name_of(proto_java_src)
            self._write_rule('%s = %s.ProtoJava(["%s"], "%s")' % (
                    java_src_var,
                    self._env_name(),
                    proto_java_src,
                    src_path))
            java_src_vars.append(java_src_var)
            self.data['java_sources'] = (
                     proto_java_src,
                     os.path.join(self.build_path, self.path),
                     self.name)
            self.data['java_sources_explict_dependency'].append(proto_java_src)
        proto_config = configparse.blade_config.get_config('proto_library_config')
        protobuf_java_libs = proto_config['protobuf_java_libs']
        if not protobuf_java_libs:
            console.error_exit('proto_library_config.protobuf_java_libs not configurated')
        self._write_rule('%s.Append(JAVACLASSPATH=%s)' % (
                self._env_name(), protobuf_java_libs))

        self._generate_generated_java_jar(self._var_name('jar'), java_src_vars)

    def _generate_java_jar(self, classes_var):
        env_name = self._env_name()
        var_name = self._var_name('jar')
        # self._write_rule('%s.Append(JARCHDIR="%s")' % (env_name, classes_dir))
        self._write_rule('%s = %s.Jar(target="%s", source=%s)' % (
            var_name, env_name, self._target_file_path(), classes_var))
        self.data['java_jar_var'] = var_name

    def _proto_php_rules(self):
        """Generate php files. """
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            proto_php_src = self._proto_gen_php_file(src)
            self._write_rule('%s.ProtoPhp(["%s"], "%s")' % (
                    self._env_name(),
                    proto_php_src,
                    src_path))

    def _proto_python_rules(self):
        """Generate python files. """
        env_name = self._env_name()
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            proto_python_src = self._proto_gen_python_file(src)
            py_src_var = self._var_name_of(src, 'python')
            self._write_rule('%s = %s.ProtoPython(["%s"], "%s")' % (
                    py_src_var,
                    env_name,
                    proto_python_src,
                    src_path))
            self.data['python_vars'].append(py_src_var)
            self.data['python_sources'].append(proto_python_src)
        py_lib_var = self._var_name('python')
        self._write_rule('%s["BASE_DIR"] = "%s"' % (env_name, self.build_path))
        self._write_rule('%s["BUILD_DIR"] = "%s"' % (env_name, self.build_path))
        self._write_rule('%s = %s.PythonLibrary(["%s"], [%s])' % (
            py_lib_var, env_name,
            self._target_file_path() + '.pylib',
            ', '.join(self.data['python_vars'])))
        self.data['python_var'] = py_lib_var

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        # Build java source according to its option
        env_name = self._env_name()

        options = self.blade.get_options()
        direct_targets = self.blade.get_direct_targets()

        if (getattr(options, 'generate_java', False) or
            self.data.get('generate_java') or
            self.key in direct_targets):
            self._proto_java_rules()

        if (getattr(options, 'generate_php', False) and
            (self.data.get('generate_php') or
             self.key in direct_targets)):
            self._proto_php_rules()

        if (getattr(options, 'generate_python', False) or
            self.data.get('generate_python') or
            self.key in direct_targets):
            self._proto_python_rules()

        self._setup_cc_flags()

        sources = []
        obj_names = []
        for src in self.srcs:
            (proto_src, proto_hdr) = self._proto_gen_files(src)

            self._write_rule('%s.Proto(["%s", "%s"], "%s")' % (
                    env_name, proto_src, proto_hdr, os.path.join(self.path, src)))
            obj_name = "%s_object" % self._var_name_of(src)
            obj_names.append(obj_name)
            self._write_rule(
                '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                'source="%s")' % (obj_name,
                                  env_name,
                                  proto_src,
                                  proto_src))
            sources.append(proto_src)

        # *.o depends on *pb.cc
        self._write_rule('%s = [%s]' % (self._objs_name(), ','.join(obj_names)))
        self._write_rule('%s.Depends(%s, %s)' % (
                         env_name, self._objs_name(), sources))

        # pb.cc depends on other proto_library
        for dep_name in self.deps:
            dep = self.target_database[dep_name]
            if not dep._generate_header_files():
                continue
            dep_var_name = dep._var_name()
            self._write_rule('%s.Depends(%s, %s)' % (
                    env_name, sources, dep_var_name))

        self._cc_library()
        options = self.blade.get_options()
        if (getattr(options, 'generate_dynamic', False) or
            self.data.get('build_dynamic', False)):
            self._dynamic_cc_library()


def proto_library(name,
                  srcs=[],
                  deps=[],
                  optimize=[],
                  deprecated=False,
                  **kwargs):
    """proto_library target. """
    proto_library_target = ProtoLibrary(name,
                                        srcs,
                                        deps,
                                        optimize,
                                        deprecated,
                                        blade.blade,
                                        kwargs)
    blade.blade.register_target(proto_library_target)


build_rules.register_function(proto_library)
