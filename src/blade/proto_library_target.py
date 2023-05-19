# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""
Define proto_library target.
"""

from __future__ import absolute_import
from __future__ import print_function

import os
import re

from blade import build_manager
from blade import build_rules
from blade import config
from blade import console
from blade import java_targets
from blade.cc_targets import CcTarget
from blade.util import var_to_list, iteritems


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
                console.error('%s: Language %s is invalid. '
                              'Protoc plugins in %s are supported by blade currently.' % (
                                  name, language, ', '.join(self.__languages)))
                continue
            self.code_generation[language] = {}
            # Note that each plugin dep should be in the global target format
            # since protoc plugin is defined in the global scope
            deps = []
            for dep in var_to_list(v['deps']):
                if dep.startswith('//'):
                    dep = dep[2:]
                if dep not in deps:
                    deps.append(dep)
            self.code_generation[language]['deps'] = deps

    def protoc_plugin_flag(self, out):
        return '--plugin=protoc-gen-%s=%s --%s_out=%s' % (
            self.name, self.path, self.name, out)

    def __repr__(self):
        # This object is a member of proto target's data, provide a textual repr here to make
        # fingerprint reproducable between each build.
        return 'ProtocPlugin(%s)' % self.__dict__


class ProtoLibrary(CcTarget, java_targets.JavaTargetMixIn):
    """
    This class manages build rules and dependencies in different languages for proto files.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 tags,
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
                src_exts=['proto'],
                deps=deps,
                visibility=visibility,
                tags=tags,
                warning='',
                defs=[],
                incs=[],
                export_incs=[],
                optimize=optimize,
                linkflags=None,
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)

        self._check_proto_srcs_name(srcs)
        if srcs:
            self.attr['public_protos'] = [self._source_file_path(s) for s in srcs]
        self._add_tags('lang:proto', 'type:library')

        proto_config = config.get_section('proto_library_config')
        protobuf_libs = var_to_list(proto_config['protobuf_libs'])
        protobuf_java_libs = var_to_list(proto_config['protobuf_java_libs'])
        protobuf_python_libs = var_to_list(proto_config['protobuf_python_libs'])

        # Implicit deps rule to thirdparty protobuf lib.
        self._add_implicit_library(protobuf_libs)
        self._add_implicit_library(protobuf_java_libs)
        self._add_implicit_library(protobuf_python_libs)

        # Normally a proto target depends on another proto target when
        # it references a message defined in that target. Then in the
        # generated code there is public API with return type/arguments
        # defined outside and in java it needs to export that dependency,
        # which is also the case for java protobuf library.
        self.attr['exported_deps'] = self._unify_deps(var_to_list(deps))
        self.attr['exported_deps'] += self._unify_deps(protobuf_java_libs)

        self._set_protoc_plugins(plugins)

        # Link all the symbols by default
        self.attr['link_all_symbols'] = True
        self.attr['deprecated'] = deprecated
        self.attr['source_encoding'] = source_encoding
        self.attr['generate_descriptors'] = generate_descriptors

        # TODO(chen3feng): Change the values to a `set` rather than separated attributes
        target_languages = var_to_list(target_languages)
        self.attr['target_languages'] = target_languages
        options = self.blade.get_options()
        self.attr['generate_java'] = 'java' in target_languages or getattr(options, 'generate_java', False)
        self.attr['generate_python'] = 'python' in target_languages or getattr(options, 'generate_python', False)
        self.attr['generate_go'] = 'go' in target_languages or getattr(options, 'generate_go', False)

        # Declare generated header files
        full_cpp_headers = []
        cpp_headers = []
        for src in self.srcs:
            full_source, full_header = self._proto_gen_cpp_files(src)
            full_cpp_headers.append(full_header)
            source, header = self._proto_gen_cpp_file_names(src)
            cpp_headers.append(header)
        self.attr['generated_hdrs'] = full_cpp_headers
        self._set_hdrs(cpp_headers)

    def _check_proto_srcs_name(self, srcs):
        """Checks whether the proto file's name ends with 'proto'."""
        for src in srcs:
            if not src.endswith('.proto'):
                self.error('Invalid proto file name %s' % src)

    def _check_proto_deps(self):
        """Only proto_library or gen_rule target is allowed as deps."""
        proto_config = config.get_section('proto_library_config')
        protobuf_libs = var_to_list(proto_config['protobuf_libs'])
        protobuf_java_libs = var_to_list(proto_config['protobuf_java_libs'])
        protobuf_libs = [self._unify_dep(d) for d in protobuf_libs + protobuf_java_libs]
        proto_deps = protobuf_libs + self.attr['protoc_plugin_deps']
        for dkey in self.deps:
            if dkey in proto_deps:
                continue
            dep = self.target_database[dkey]
            if dkey not in self._implicit_deps and dep.type not in ('proto_library', 'gen_rule'):
                self.error('Invalid dep %s. proto_library can only depend on proto_library '
                           'or gen_rule.' % dep.fullname)

    def _set_protoc_plugins(self, plugins):
        """Handle protoc plugins and corresponding dependencies."""
        plugins = var_to_list(plugins)
        self.attr['protoc_plugins'] = plugins
        protoc_plugin_config = config.get_section('protoc_plugin_config')
        protoc_plugins = []
        protoc_plugin_deps, protoc_plugin_java_deps = set(), set()
        for plugin in plugins:
            if plugin not in protoc_plugin_config:
                self.error('Unknown plugin %s' % plugin)
                continue
            p = protoc_plugin_config[plugin]
            protoc_plugins.append(p)
            for language, v in iteritems(p.code_generation):
                for key in v['deps']:
                    if key not in self.deps:
                        self.deps.append(key)
                    protoc_plugin_deps.add(key)
                    if language == 'java':
                        protoc_plugin_java_deps.add(key)
        self.attr['protoc_plugin_deps'] = list(protoc_plugin_deps)
        self.attr['exported_deps'] += list(protoc_plugin_java_deps)
        self.data['protoc_plugin_objects'] = protoc_plugins

    def _prepare_to_generate_rule(self):
        CcTarget._prepare_to_generate_rule(self)
        self._check_proto_deps()

    def _expand_deps_generation(self):
        if self.attr['generate_java']:
            self._expand_deps_java_generation()

    def _proto_gen_cpp_files(self, src):
        """_proto_gen_cpp_files."""
        proto_name = src[:-6]
        return (self._target_file_path('%s.pb.cc' % proto_name),
                self._target_file_path('%s.pb.h' % proto_name))

    def _proto_gen_php_file(self, src):
        """Generate the php file name."""
        proto_name = src[:-6]
        return self._target_file_path('%s.pb.php' % proto_name)

    def _proto_gen_python_file(self, src):
        """Generate the python file name."""
        proto_name = src[:-6]
        return self._target_file_path('%s_pb2.py' % proto_name)

    def _proto_gen_descriptor_file(self, name):
        """Generate the descriptor file name."""
        return self._target_file_path('%s.descriptors.pb' % name)

    def _get_java_pack_deps(self):
        return self._get_pack_deps()

    def _get_java_package_name(self, content):
        """Get the java package name from proto file if it is specified."""
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
        self.error('"go_package" is mandatory to generate golang code '
                   'in protocol buffers but is missing in %s.' % path)
        return ''

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
        """Generate the java files name of the proto library."""
        # FIXME: Handle utf-8 file decode error in python3
        with open(self._source_file_path(src)) as f:
            content = f.read()
        package_dir = self._get_java_package_name(content).replace('.', '/')
        class_name = self._proto_java_gen_class_name(src, content)
        java_name = '%s.java' % class_name
        return package_dir, java_name

    def protoc_direct_dependencies(self):
        """
        Calculate direct proto dependencies for this target, recompile protos of this target
        when any of these dependencies is changed.
        """
        # TODO: protoc 3.0.0+'s `--dependency_out` option generates more accurate dependency,
        # which can be used to reduce false dependency.

        # Including self's proto files because if there are multiple proto files in this target,
        # there may be import relationships between these files.
        key = 'protoc_direct_dependencies'  # Cache the result
        if key in self.data:
            return self.data[key][:]
        self_protos = self.attr.get('public_protos')
        protos = self_protos[:] if len(self_protos) > 1 else []
        for key in self.deps:
            dep = self.target_database[key]
            protos += dep.attr.get('public_protos', [])
        self.data[key] = protos
        return protos[:]

    def _proto_descriptor_rules(self):
        inputs = [self._source_file_path(s) for s in self.srcs]
        output = self._proto_gen_descriptor_file(self.name)
        self.generate_build('protodescriptors', output, inputs=inputs, variables={'first': inputs[0]})

    def _protoc_plugin_parameters(self, language):
        """Return a tuple of (plugin paths, vars) used as parameters for ninja build."""
        paths, vars = [], {}
        for p in self.data['protoc_plugin_objects']:
            if language in p.code_generation:
                paths.append(p.path)
                flag_key = 'protoc%spluginflags' % language
                # For Java, we need to be consistent with native java output directory
                # which is the build target directory for insertion points to be effected.
                # See `protojava` rules for details
                if language == 'java':
                    flag_value = p.protoc_plugin_flag(self._target_dir())
                else:
                    flag_value = p.protoc_plugin_flag(self.build_dir)
                vars[flag_key] = vars[flag_key] + ' ' + flag_value if flag_key in vars else flag_value
        return paths, vars

    def _add_protoc_direct_dependencies(self, vars):
        """ Add a `--direct_dependencies` optiopn to protocflags.

        This option enforces correct dependency is declared for any imported proto file.
        """
        # Because cpp_out is always generated, we needn't add this option to other language's out.
        if config.get_item('proto_library_config', 'protoc_direct_dependencies'):
            dependencies = self.protoc_direct_dependencies()
            dependencies += config.get_item('proto_library_config', 'well_known_protos')
            vars['protocflags'] = '--direct_dependencies %s' % ':'.join(dependencies)

    def _proto_cpp_rules(self):
        plugin_paths, vars = self._protoc_plugin_parameters('cpp')
        self._add_protoc_direct_dependencies(vars)
        implicit_deps = self.protoc_direct_dependencies()
        implicit_deps.extend(plugin_paths)
        cpp_sources = []
        for src in self.srcs:
            full_source, full_header = self._proto_gen_cpp_files(src)
            self.generate_build('proto', [full_source, full_header],
                                inputs=self._source_file_path(src),
                                implicit_deps=implicit_deps, variables=vars)
            source, header = self._proto_gen_cpp_file_names(src)
            cpp_sources.append(source)
        objs = self._generated_cc_objects(cpp_sources, generated_headers=self.attr['generated_hdrs'])
        self._cc_library(objs)

    def _proto_java_rules(self):
        plugin_paths, vars = self._protoc_plugin_parameters('java')
        implicit_deps = self.protoc_direct_dependencies()
        implicit_deps.extend(plugin_paths)
        java_sources = []
        for src in self.srcs:
            input = self._source_file_path(src)
            package_dir, java_name = self._proto_java_gen_file(src)
            output = self._target_file_path(os.path.join(os.path.dirname(src), package_dir, java_name))
            self.generate_build('protojava', output, inputs=input,
                                implicit_deps=implicit_deps, variables=vars)
            java_sources.append(output)

        jar = self._build_jar(inputs=java_sources, source_encoding=self.attr.get('source_encoding'))
        self._add_target_file('jar', jar)

    def _proto_python_rules(self):
        # plugin, vars = self._protoc_plugin_parameters('python')
        implicit_deps = self.protoc_direct_dependencies()
        generated_pys = []
        for proto in self.srcs:
            input = self._source_file_path(proto)
            output = self._proto_gen_python_file(proto)
            self.generate_build('protopython', output, inputs=input)
            generated_pys.append(output)
        pylib = self._target_file_path(self.name + '.pylib')
        self.generate_build('pythonlibrary', pylib, inputs=generated_pys,
                            implicit_deps=implicit_deps, variables={'basedir': self.build_dir})
        self._add_target_file('pylib', pylib)

    def _proto_go_rules(self):
        go_home = config.get_item('go_config', 'go_home')
        protobuf_go_path = config.get_item('proto_library_config', 'protobuf_go_path')
        generated_goes = []
        for src in self.srcs:
            path = self._source_file_path(src)
            package = self._get_go_package_name(path)
            if not package:
                continue
            if not package.startswith(protobuf_go_path):
                self.warning('go_package "%s" is not starting with "%s" in %s' % (
                             package, protobuf_go_path, src))
            basename = os.path.basename(src)
            output = os.path.join(go_home, 'src', package, '%s.pb.go' % basename[:-6])
            self.generate_build('protogo', output, inputs=path)
            generated_goes.append(output)
        self._add_target_file('gopkg', generated_goes)

    def _proto_rules(self):
        """Generate ninja rules for other languages if needed."""
        self._proto_cpp_rules()

        if self.attr.get('generate_java') or self.attr.get('generate_scala'):
            self._proto_java_rules()

        if self.attr.get('generate_python'):
            self._proto_python_rules()

        if self.attr.get('generate_go'):
            self._proto_go_rules()

        if self.attr['generate_descriptors']:
            self._proto_descriptor_rules()

    def _proto_gen_cpp_file_names(self, source):
        """Return just file names"""
        base = source[:-6]
        return ['%s.pb.cc' % base, '%s.pb.h' % base]

    def generate(self):
        """Generate build code for proto files."""
        self._check_deprecated_deps()
        self._check_proto_deps()
        if not self.srcs:
            return

        self._proto_rules()


def proto_library(
        name,
        srcs=[],
        deps=[],
        visibility=None,
        tags=[],
        optimize=None,
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
            tags=tags,
            optimize=optimize,
            deprecated=deprecated,
            generate_descriptors=generate_descriptors,
            target_languages=target_languages,
            plugins=plugins,
            source_encoding=source_encoding,
            kwargs=kwargs)
    build_manager.instance.register_target(proto_library_target)


build_rules.register_function(proto_library)
