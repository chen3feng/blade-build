# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define proto_library target
"""


import os
import blade

import console
import configparse
import build_rules
from blade_util import var_to_list
from cc_targets import CcTarget


class ProtoLibrary(CcTarget):
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
        protobuf_lib = var_to_list(proto_config['protobuf_libs'])

        # Hardcode deps rule to thirdparty protobuf lib.
        self._add_hardcode_library(protobuf_lib)

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

    def _proto_gen_files(self, path, src):
        """_proto_gen_files. """
        proto_name = src[:-6]
        return (self._target_file_path(path, '%s.pb.cc' % proto_name),
                self._target_file_path(path, '%s.pb.h' % proto_name))

    def _proto_gen_php_file(self, path, src):
        """Generate the php file name. """
        proto_name = src[:-6]
        return self._target_file_path(path, '%s.pb.php' % proto_name)

    def _proto_gen_python_file(self, path, src):
        """Generate the python file name. """
        proto_name = src[:-6]
        return self._target_file_path(path, '%s_pb2.py' % proto_name)

    def _get_java_package_name(self, src):
        """Get the java package name from proto file if it is specified. """
        package_name_java = 'java_package'
        package_name = 'package'
        if not os.path.isfile(src):
            return ''
        package_line = ''
        package = ''
        normal_package_line = ''
        for line in open(src):
            line = line.strip()
            if line.startswith('//'):
                continue
            pos = line.find('//')
            if pos != -1:
                line = line[0:pos]
            if package_name_java in line:
                package_line = line
                break
            if line.startswith(package_name):
                normal_package_line = line

        if package_line:
            package = package_line.split('=')[1].strip().strip(r'\'";')
        elif normal_package_line:
            package = normal_package_line.split(' ')[1].strip().strip(';')

        package = package.replace('.', '/')

        return package

    def _proto_java_gen_file(self, path, src, package):
        """Generate the java files name of the proto library. """
        proto_name = src[:-6]
        base_name = os.path.basename(proto_name)
        base_name = ''.join(base_name.title().split('_'))
        base_name = '%s.java' % base_name
        dir_name = os.path.join(path, package)
        proto_name = os.path.join(dir_name, base_name)
        return os.path.join(self.build_path, proto_name)

    def _proto_java_rules(self):
        """Generate scons rules for the java files from proto file. """
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            package_dir = self._get_java_package_name(src_path)
            proto_java_src_package = self._proto_java_gen_file(self.path,
                                                               src,
                                                               package_dir)

            self._write_rule('%s.ProtoJava(["%s"], "%s")' % (
                    self._env_name(),
                    proto_java_src_package,
                    src_path))

            self.data['java_sources'] = (
                     os.path.dirname(proto_java_src_package),
                     os.path.join(self.build_path, self.path),
                     self.name)
            self.data['java_sources_explict_dependency'].append(proto_java_src_package)

    def _proto_php_rules(self):
        """Generate php files. """
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            proto_php_src = self._proto_gen_php_file(self.path, src)
            self._write_rule('%s.ProtoPhp(["%s"], "%s")' % (
                    self._env_name(),
                    proto_php_src,
                    src_path))

    def _proto_python_rules(self):
        """Generate python files. """
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            proto_python_src = self._proto_gen_python_file(self.path, src)
            py_cmd_var = '%s_python' % self._generate_variable_name(
                    self.path, self.name)
            self._write_rule('%s = %s.ProtoPython(["%s"], "%s")' % (
                    py_cmd_var,
                    self._env_name(),
                    proto_python_src,
                    src_path))
            self.data['python_vars'].append(py_cmd_var)
            self.data['python_sources'].append(proto_python_src)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        # Build java source according to its option
        env_name = self._env_name()

        self.options = self.blade.get_options()
        self.direct_targets = self.blade.get_direct_targets()

        if (getattr(self.options, 'generate_java', False) or
            self.data.get('generate_java') or
            self.key in self.direct_targets):
            self._proto_java_rules()

        if (getattr(self.options, 'generate_php', False) and
            (self.data.get('generate_php') or
             self.key in self.direct_targets)):
            self._proto_php_rules()

        if (getattr(self.options, 'generate_python', False) or
            self.data.get('generate_python') or
            self.key in self.direct_targets):
            self._proto_python_rules()

        self._setup_cc_flags()

        sources = []
        obj_names = []
        for src in self.srcs:
            (proto_src, proto_hdr) = self._proto_gen_files(self.path, src)

            self._write_rule('%s.Proto(["%s", "%s"], "%s")' % (
                    env_name,
                    proto_src,
                    proto_hdr,
                    os.path.join(self.path, src)))
            obj_name = "%s_object" % self._generate_variable_name(
                self.path, src)
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
            dep_var_name = self._generate_variable_name(dep.path, dep.name)
            self._write_rule('%s.Depends(%s, %s)' % (
                    self._env_name(),
                    sources,
                    dep_var_name))

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
