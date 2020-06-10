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
                 visibility,
                 optimize,
                 deprecated,
                 generate_descriptors,
                 target_languages,
                 plugins,
                 source_encoding,
                 kwargs):
        """Init method.

        Init the proto target.

        """
        # pylint: disable=too-many-locals
        srcs = var_to_list(srcs)
        super(ProtoLibrary, self).__init__(
                name=name,
                type='proto_library',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning='',
                defs=[],
                incs=[],
                export_incs=[],
                optimize=optimize,
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)

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

        # TODO(chen3feng): Change the values to a `set` rather than separated attributes
        target_languages = set(var_to_list(target_languages))
        self.data['generate_java'] = 'java' in target_languages
        self.data['generate_python'] = 'python' in target_languages
        self.data['generate_go'] = 'go' in target_languages

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

    def _expand_deps_generation(self):
        if self.data['generate_java']:
            self._expand_deps_java_generation()

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

    def protoc_direct_dependencies(self):
        protos = self.data.get('public_protos')[:]
        for key in self.deps:
            dep = self.target_database[key]
            protos += dep.data.get('public_protos', [])
        return protos

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
                flag = p.protoc_plugin_flag(self.build_dir)
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
        pylib = self._target_file_path(self.name + '.pylib')
        self.ninja_build('pythonlibrary', pylib, inputs=generated_pys,
                         variables={'basedir': self.build_dir})
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


def proto_library(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        optimize=[],
        deprecated=False,
        generate_descriptors=False,
        target_languages=None,
        plugins=[],
        source_encoding='iso-8859-1',
        **kwargs):
    """proto_library target.
    Args:
        generate_descriptors (bool): Whether generate binary protobuf descriptors.
        target_languages (Sequence[str]): Code for target languages to be generated, such as
            `java`, `python`, see protoc's `--xx_out`s.
            NOTE: The `cpp` target code is always generated.
    """
    proto_library_target = ProtoLibrary(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            optimize=optimize,
            deprecated=deprecated,
            generate_descriptors=generate_descriptors,
            target_languages=target_languages,
            plugins=plugins,
            source_encoding=source_encoding,
            kwargs=kwargs)
    build_manager.instance.register_target(proto_library_target)


build_rules.register_function(proto_library)
