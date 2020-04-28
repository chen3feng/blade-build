# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define proto_library target
"""

from __future__ import absolute_import

import os
import re

from blade import build_manager
from blade import build_rules
from blade import config
from blade import console
from blade import java_targets
from blade.blade_util import var_to_list, iteritems
from blade.cc_targets import CcTarget


class ProtocPlugin(object):
    """A helper class for protoc plugin.

    Currently blade only supports protoc plugin which generates
    code by use of @@protoc_insertion_point mechanism. See
    https://developers.google.com/protocol-buffers/docs/reference/cpp/google.protobuf.compiler.plugin.pb
    for more details.

    """

    __languages = ['cpp', 'java', 'python']

    def __init__(self,
                 name,
                 path,
                 code_generation):
        self.name = name
        self.path = path
        assert isinstance(code_generation, dict)
        self.code_generation = {}
        for language, v in iteritems(code_generation):
            if language not in self.__languages:
                console.error_exit('%s: Language %s is invalid. '
                                   'Protoc plugins in %s are supported by blade currently.' % (
                                       name, language, ', '.join(self.__languages)))
            self.code_generation[language] = {}
            # Note that each plugin dep should be in the global target format
            # since protoc plugin is defined in the global scope
            deps = []
            for dep in var_to_list(v['deps']):
                if dep.startswith('//'):
                    dep = dep[2:]
                key = tuple(dep.split(':'))
                if key not in deps:
                    deps.append(key)
            self.code_generation[language]['deps'] = deps

    def protoc_plugin_flag(self, out):
        return '--plugin=protoc-gen-%s=%s --%s_out=%s' % (
            self.name, self.path, self.name, out)


class ProtoLibrary(CcTarget, java_targets.JavaTargetMixIn):
    """
    This class manages build rules and dependencies in different languages for proto files.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 optimize,
                 deprecated,
                 generate_descriptors,
                 plugins,
                 source_encoding,
                 blade,
                 kwargs):
        """Init method.

        Init the proto target.

        """
        # pylint: disable=too-many-locals
        srcs = var_to_list(srcs)
        CcTarget.__init__(self,
                          name,
                          'proto_library',
                          srcs,
                          deps,
                          None,
                          '',
                          [], [], [], optimize, [], [],
                          blade,
                          kwargs)

        self._check_proto_srcs_name(srcs)
        if srcs:
            self.data['public_protos'] = [self._source_file_path(s) for s in srcs]

        proto_config = config.get_section('proto_library_config')
        protobuf_libs = var_to_list(proto_config['protobuf_libs'])
        protobuf_java_libs = var_to_list(proto_config['protobuf_java_libs'])
        protobuf_python_libs = var_to_list(proto_config['protobuf_python_libs'])

        # Hardcode deps rule to thirdparty protobuf lib.
        self._add_hardcode_library(protobuf_libs)
        self._add_hardcode_java_library(protobuf_java_libs)
        self._add_hardcode_library(protobuf_python_libs)

        # Normally a proto target depends on another proto target when
        # it references a message defined in that target. Then in the
        # generated code there is public API with return type/arguments
        # defined outside and in java it needs to export that dependency,
        # which is also the case for java protobuf library.
        self.data['exported_deps'] = self._unify_deps(var_to_list(deps))
        self.data['exported_deps'] += self._unify_deps(protobuf_java_libs)

        self._handle_protoc_plugins(var_to_list(plugins))

        # Link all the symbols by default
        self.data['link_all_symbols'] = True
        self.data['deprecated'] = deprecated
        self.data['source_encoding'] = source_encoding
        self.data['java_sources_explict_dependency'] = []
        self.data['python_vars'] = []
        self.data['python_sources'] = []
        self.data['generate_descriptors'] = generate_descriptors

    def _check_proto_srcs_name(self, srcs):
        """Checks whether the proto file's name ends with 'proto'. """
        for src in srcs:
            if not src.endswith('.proto'):
                self.error_exit('Invalid proto file name %s' % src)

    def _check_proto_deps(self):
        """Only proto_library or gen_rule target is allowed as deps. """
        proto_config = config.get_section('proto_library_config')
        protobuf_libs = var_to_list(proto_config['protobuf_libs'])
        protobuf_java_libs = var_to_list(proto_config['protobuf_java_libs'])
        protobuf_libs = [self._unify_dep(d) for d in protobuf_libs + protobuf_java_libs]
        proto_deps = protobuf_libs + self.data['protoc_plugin_deps']
        for dkey in self.deps:
            if dkey in proto_deps:
                continue
            dep = self.target_database[dkey]
            if dep.type != 'proto_library' and dep.type != 'gen_rule':
                self.error_exit('Invalid dep %s. Proto_library can only depend on proto_library '
                                'or gen_rule.' % dep.fullname)

    def _handle_protoc_plugins(self, plugins):
        """Handle protoc plugins and corresponding dependencies. """
        protoc_plugin_config = config.get_section('protoc_plugin_config')
        protoc_plugins = []
        protoc_plugin_deps, protoc_plugin_java_deps = set(), set()
        for plugin in plugins:
            if plugin not in protoc_plugin_config:
                self.error_exit('Unknown plugin %s' % plugin)
            p = protoc_plugin_config[plugin]
            protoc_plugins.append(p)
            for language, v in iteritems(p.code_generation):
                for key in v['deps']:
                    if key not in self.deps:
                        self.deps.append(key)
                    if key not in self.expanded_deps:
                        self.expanded_deps.append(key)
                    protoc_plugin_deps.add(key)
                    if language == 'java':
                        protoc_plugin_java_deps.add(key)
        self.data['protoc_plugin_deps'] = list(protoc_plugin_deps)
        self.data['exported_deps'] += list(protoc_plugin_java_deps)
        self.data['protoc_plugins'] = protoc_plugins

    def _prepare_to_generate_rule(self):
        CcTarget._prepare_to_generate_rule(self)
        self._check_proto_deps()

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

    def _proto_gen_go_file(self, src):
        """Generate the go file name. """
        proto_name = src[:-6]
        return self._target_file_path('%s.pb.go' % proto_name)

    def _proto_gen_descriptor_file(self, name):
        """Generate the descriptor file name. """
        return self._target_file_path('%s.descriptors.pb' % name)

    def _get_java_pack_deps(self):
        return self._get_pack_deps()

    def _get_java_package_name(self, content):
        """Get the java package name from proto file if it is specified. """
        java_package_pattern = r'^\s*option\s+java_package\s*=\s*["\']([\w.]+)'
        m = re.search(java_package_pattern, content, re.MULTILINE)
        if m:
            return m.group(1)

        package_pattern = r'^\s*package\s+([\w.]+)'
        m = re.search(package_pattern, content, re.MULTILINE)
        if m:
            return m.group(1)

        return ''

    def _get_go_package_name(self, path):
        with open(path) as f:
            content = f.read()
        pattern = r'^\s*option\s+go_package\s*=\s*"([\w./]+)";'
        m = re.search(pattern, content, re.MULTILINE)
        if m:
            return m.group(1)
        else:
            self.error_exit('"go_package" is mandatory to generate golang code '
                            'in protocol buffers but is missing in %s.' % path)

    def _proto_java_gen_class_name(self, src, content):
        """Get generated java class name"""
        pattern = r'^\s*option\s+java_outer_classname\s*=\s*[\'"](\w+)["\']'
        m = re.search(pattern, content, re.MULTILINE)
        if m:
            return m.group(1)
        proto_name = src[:-6]
        base_name = os.path.basename(proto_name)
        return ''.join([p[0].upper() + p[1:] for p in base_name.split('_') if p])

    def _proto_java_gen_file(self, src):
        """Generate the java files name of the proto library. """
        with open(self._source_file_path(src)) as f:
            content = f.read()
        package_dir = self._get_java_package_name(content).replace('.', '/')
        class_name = self._proto_java_gen_class_name(src, content)
        java_name = '%s.java' % class_name
        return package_dir, java_name

    def _proto_java_rules(self):
        """Generate scons rules for the java files from proto file. """
        env_name = self._env_name()
        java_srcs = []
        java_src_vars = []
        for src in self.srcs:
            src_path = os.path.join(self.path, src)
            package_dir, java_name = self._proto_java_gen_file(src)
            proto_java_src = self._target_file_path(
                os.path.join(os.path.dirname(src), package_dir, java_name))
            java_srcs.append(proto_java_src)
            java_src_var = self._var_name_of(proto_java_src)
            self._write_rule('%s = %s.ProtoJava("%s", "%s")' % (
                java_src_var, env_name, proto_java_src, src_path))
            java_src_vars.append(java_src_var)
            self.data['java_sources'] = (
                proto_java_src,
                os.path.join(self.build_path, self.path),
                self.name)
            self.data['java_sources_explict_dependency'].append(proto_java_src)

        self._generate_java_versions()
        self._generate_java_source_encoding()
        dep_jar_vars, dep_jars = self._get_compile_deps()
        self._generate_java_classpath(dep_jar_vars, dep_jars)
        var_name = self._var_name('jar')
        self._generate_generated_java_jar(var_name, java_src_vars)
        self._generate_java_depends(var_name, dep_jar_vars, dep_jars, '', '')
        self._add_target_var('jar', var_name)

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

    def _proto_go_rules(self):
        """Generate go files. """
        env_name = self._env_name()
        var_name = self._var_name('go')
        go_home = config.get_item('go_config', 'go_home')
        if not go_home:
            self.error_exit("'go_home' is not configured")
        proto_go_path = config.get_item('proto_library_config', 'protobuf_go_path')
        go_module_enabled = config.get_item('go_config', 'go_module_enabled')
        go_module_relpath = config.get_item('go_config', 'go_module_relpath')
        self._write_rule('%s.Replace(PROTOBUFGOPATH="%s")' % (env_name, proto_go_path))
        self._write_rule('%s = []' % var_name)
        for src in self.srcs:
            proto_src = os.path.join(self.path, src)
            go_src = self._proto_gen_go_file(src)
            go_src_var = self._var_name_of(src, 'go_src')
            self._write_rule('%s = %s.ProtoGo("%s", "%s")' % (
                go_src_var, env_name, go_src, proto_src))
            # Copy the generated go sources to $GOPATH
            # according to the standard go directory layout
            proto_dir = os.path.dirname(src)
            proto_name = os.path.basename(src)
            if go_module_enabled and not go_module_relpath:
                go_dst = os.path.join(proto_go_path, self.path,
                                      proto_dir, proto_name.replace('.', '_'),
                                      os.path.basename(go_src))
            else:
                go_dst = os.path.join(go_home, 'src', proto_go_path, self.path,
                                      proto_dir, proto_name.replace('.', '_'),
                                      os.path.basename(go_src))
            go_dst_var = self._var_name_of(src, 'go_dst')
            self._write_rule('%s = %s.ProtoGoSource("%s", %s)' % (
                go_dst_var, env_name, go_dst, go_src_var))
            self._write_rule('%s.append(%s)' % (var_name, go_dst_var))
        self._add_target_var('go', var_name)

    def _proto_descriptor_rules(self):
        """Generate descriptor files. """
        proto_srcs = [os.path.join(self.path, src) for src in self.srcs]
        proto_descriptor_file = self._proto_gen_descriptor_file(self.name)
        self._write_rule('%s.ProtoDescriptors("%s", %s)' % (
            self._env_name(), proto_descriptor_file, proto_srcs))

    def _protoc_plugin_rules(self):
        """Generate scons rules for each protoc plugin. """
        env_name = self._env_name()
        protoc_plugin_config = config.get_section('protoc_plugin_config')
        for plugin in self.data['protoc_plugins']:
            p = protoc_plugin_config[plugin]
            for language in p.code_generation:
                self._write_rule('%s.Append(PROTOC%sPLUGINFLAGS = "%s ")' % (
                    env_name, language.upper(),
                    p.protoc_plugin_flag(self.build_path)))

    def protoc_direct_dependencies(self):
        protos = self.data.get('public_protos')[:]
        for key in self.deps:
            dep = self.target_database[key]
            protos += dep.data.get('public_protos', [])
        return protos

    def _protoc_direct_dependencies_rules(self):
        if config.get_item('proto_library_config', 'protoc_direct_dependencies'):
            dependencies = self.protoc_direct_dependencies()
            dependencies += config.get_item('proto_library_config', 'well_known_protos')
            env_name = self._env_name()
            self._write_rule('%s.Append(PROTOCFLAGS="--direct_dependencies %s")' % (
                env_name, ':'.join(dependencies)))

    def scons_rules(self):
        """Generates the scons rules according to user options. """
        self._prepare_to_generate_rule()
        if not self.srcs:
            return

        env_name = self._env_name()
        options = self.blade.get_options()

        self._protoc_direct_dependencies_rules()
        self._protoc_plugin_rules()

        if (getattr(options, 'generate_java', False) or
                self.data.get('generate_java') or
                self.data.get('generate_scala')):
            self._proto_java_rules()

        if (getattr(options, 'generate_php', False) or
                self.data.get('generate_php')):
            self._proto_php_rules()

        if (getattr(options, 'generate_python', False) or
                self.data.get('generate_python')):
            self._proto_python_rules()

        if (getattr(options, 'generate_go', False) or
                self.data.get('generate_go')):
            self._proto_go_rules()

        if self.data['generate_descriptors']:
            self._proto_descriptor_rules()

        self._setup_cc_flags()

        sources = []
        objs = []
        for src in self.srcs:
            (proto_src, proto_hdr) = self._proto_gen_files(src)

            self._write_rule('%s.Proto(["%s", "%s"], "%s")' % (
                env_name, proto_src, proto_hdr, os.path.join(self.path, src)))
            obj_name = "obj_%s" % self._var_name_of(src)
            objs.append(obj_name)
            self._write_rule(
                '%s = %s.SharedObject(target="%s" + top_env["OBJSUFFIX"], '
                'source="%s")' % (obj_name,
                                  env_name,
                                  proto_src,
                                  proto_src))
            sources.append(proto_src)

        if len(objs) == 1:
            self._set_objs_name(objs[0])
            objs_name = objs[0]
        else:
            objs_name = self._objs_name()
            self._write_rule('%s = [%s]' % (objs_name, ','.join(objs)))

        # *.o depends on *.pb.cc
        self._write_rule('%s.Depends(%s, %s)' % (env_name, objs_name, sources))
        # pb.cc depends on other proto_library
        self._generate_generated_header_files_depends(sources)
        self._cc_library()

    def ninja_proto_descriptor_rules(self):
        inputs = [self._source_file_path(s) for s in self.srcs]
        output = self._proto_gen_descriptor_file(self.name)
        self.ninja_build('protodescriptors', output, inputs=inputs, variables={'first': inputs[0]})

    def ninja_protoc_plugin_parameters(self, language):
        """Return a tuple of (plugin path, vars) used as parameters for ninja build. """
        path, vars = '', {}
        for p in self.data['protoc_plugins']:
            if language in p.code_generation:
                path = p.path
                flag = p.protoc_plugin_flag(self.build_path)
                vars = {'protoc%spluginflags' % language: flag}
                break
        return path, vars

    def ninja_protoc_direct_dependencies(self, vars):
        if config.get_item('proto_library_config', 'protoc_direct_dependencies'):
            dependencies = self.protoc_direct_dependencies()
            dependencies += config.get_item('proto_library_config', 'well_known_protos')
            vars['protocflags'] = '--direct_dependencies %s' % ':'.join(dependencies)

    def ninja_proto_java_rules(self):
        java_sources, implicit_deps = [], []
        plugin, vars = self.ninja_protoc_plugin_parameters('java')
        if plugin:
            implicit_deps.append(plugin)
        for src in self.srcs:
            input = self._source_file_path(src)
            package_dir, java_name = self._proto_java_gen_file(src)
            output = self._target_file_path(os.path.join(os.path.dirname(src), package_dir, java_name))
            self.ninja_build('protojava', output, inputs=input,
                             implicit_deps=implicit_deps, variables=vars)
            java_sources.append(output)

        jar = self.ninja_build_jar(inputs=java_sources,
                                   source_encoding=self.data.get('source_encoding'))
        self._add_target_file('jar', jar)

    def ninja_proto_python_rules(self):
        # plugin, vars = self.ninja_protoc_plugin_parameters('python')
        generated_pys = []
        for proto in self.srcs:
            input = self._source_file_path(proto)
            output = self._proto_gen_python_file(proto)
            self.ninja_build('protopython', output, inputs=input)
            generated_pys.append(output)
        pylib = self._target_file_path() + '.pylib'
        self.ninja_build('pythonlibrary', pylib, inputs=generated_pys,
                         variables={'pythonbasedir': self.build_path})
        self._add_target_file('pylib', pylib)

    def ninja_proto_go_rules(self):
        go_home = config.get_item('go_config', 'go_home')
        protobuf_go_path = config.get_item('proto_library_config', 'protobuf_go_path')
        generated_goes = []
        for src in self.srcs:
            path = self._source_file_path(src)
            package = self._get_go_package_name(path)
            if not package.startswith(protobuf_go_path):
                self.warning('go_package "%s" is not starting with "%s" in %s' % (
                             package, protobuf_go_path, src))
            basename = os.path.basename(src)
            output = os.path.join(go_home, 'src', package, '%s.pb.go' % basename[:-6])
            self.ninja_build('protogo', output, inputs=path)
            generated_goes.append(output)
        self._add_target_file('gopkg', generated_goes)

    def ninja_proto_rules(self, options):
        """Generate ninja rules for other languages if needed. """
        if (getattr(options, 'generate_java', False) or
                self.data.get('generate_java') or
                self.data.get('generate_scala')):
            self.ninja_proto_java_rules()

        if (getattr(options, 'generate_python', False) or
                self.data.get('generate_python')):
            self.ninja_proto_python_rules()

        if (getattr(options, 'generate_go', False) or
                self.data.get('generate_go')):
            self.ninja_proto_go_rules()

        if self.data['generate_descriptors']:
            self.ninja_proto_descriptor_rules()

    def _proto_gen_file_names(self, source):
        base = source[:-6]
        return ['%s.pb.h' % base, '%s.pb.cc' % base]

    def ninja_rules(self):
        """Generate ninja rules for proto files. """
        self._check_deprecated_deps()
        self._check_proto_deps()
        if not self.srcs:
            return

        plugin, vars = self.ninja_protoc_plugin_parameters('cpp')
        self.ninja_protoc_direct_dependencies(vars)
        cpp_sources, cpp_headers, implicit_deps = [], [], []
        if plugin:
            implicit_deps.append(plugin)
        for src in self.srcs:
            source, header = self._proto_gen_files(src)
            self.ninja_build('proto', [source, header],
                             inputs=self._source_file_path(src),
                             implicit_deps=implicit_deps, variables=vars)
            cpp_headers.append(header)
            self.data['generated_hdrs'].append(header)
            names = self._proto_gen_file_names(src)
            cpp_sources.append(names[1])
        self._cc_objects_ninja(cpp_sources, True, generated_headers=cpp_headers)
        self._cc_library_ninja()
        self.ninja_proto_rules(self.blade.get_options())


def proto_library(name,
                  srcs=[],
                  deps=[],
                  optimize=[],
                  deprecated=False,
                  generate_descriptors=False,
                  plugins=[],
                  source_encoding='iso-8859-1',
                  **kwargs):
    """proto_library target. """
    proto_library_target = ProtoLibrary(name,
                                        srcs,
                                        deps,
                                        optimize,
                                        deprecated,
                                        generate_descriptors,
                                        plugins,
                                        source_encoding,
                                        build_manager.instance,
                                        kwargs)
    build_manager.instance.register_target(proto_library_target)


build_rules.register_function(proto_library)
