# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define lex_yacc_library target
"""

from __future__ import absolute_import

from blade import build_manager
from blade import build_rules
from blade import console
from blade.blade_util import var_to_list
from blade.cc_targets import CcTarget


class LexYaccLibrary(CcTarget):
    """A scons cc target subclass.

    This class is derived from SconsCCTarget and it generates lex yacc rules.

    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 warning,
                 defs,
                 incs,
                 allow_undefined,
                 recursive,
                 prefix,
                 lexflags,
                 yaccflags,
                 blade,
                 kwargs):
        """Init method.

        Init the cc lex yacc target

        """
        if (len(srcs) != 2 or
                (not (srcs[0].endswith('.l') or srcs[0].endswith('.ll'))) or
                (not (srcs[1].endswith('.y') or srcs[1].endswith('.yy')))):
            self.error_exit('srcs for lex_yacc_library must be a pair of [lex_file, yacc_file]')

        CcTarget.__init__(self,
                          name,
                          'lex_yacc_library',
                          srcs,
                          deps,
                          None,
                          warning,
                          defs,
                          incs,
                          [], [], [], [],
                          blade,
                          kwargs)

        self.data['recursive'] = recursive
        self.data['prefix'] = prefix
        self.data['lexflags'] = var_to_list(lexflags)
        self.data['yaccflags'] = var_to_list(yaccflags)
        self.data['prefix'] = prefix
        self.data['allow_undefined'] = allow_undefined
        self.data['link_all_symbols'] = True

    def _lex_flags(self):
        """Return lex flags according to the options. """
        lex_flags = list(self.data['lexflags'])
        if self.data.get('recursive'):
            lex_flags.append('-R')
        prefix = self.data.get('prefix')
        if prefix:
            lex_flags.append('-P %s' % prefix)
        return lex_flags

    def _yacc_flags(self):
        """Return yacc flags according to the options. """
        yacc_flags = list(self.data['yaccflags'])
        yacc_flags.append('-d')
        prefix = self.data.get('prefix')
        if prefix:
            yacc_flags.append('-p %s' % prefix)
        return yacc_flags

    def _generate_lex_yacc_flags(self, lex_flags, yacc_flags):
        env_name = self._env_name()
        self._write_rule('%s.Replace(LEXFLAGS=%s)' % (env_name, lex_flags))
        self._write_rule('%s.Replace(YACCFLAGS=%s)' % (env_name, yacc_flags))

    def _generate_cc_source(self, var_name, src):
        """Generate scons rules for cc source from lex/yacc source. """
        env_name = self._env_name()
        source = self._source_file_path(src)
        target = self._target_file_path(src)
        if src.endswith('.l') or src.endswith('.y'):
            rule = 'target = "%s" + top_env["CFILESUFFIX"], source = "%s"' % (target, source)
            self._write_rule('%s = %s.CFile(%s)' % (var_name, env_name, rule))
        elif src.endswith('.ll') or src.endswith('.yy'):
            rule = 'target = "%s" + top_env["CXXFILESUFFIX"], source = "%s"' % (target, source)
            self._write_rule('%s = %s.CXXFile(%s)' % (var_name, env_name, rule))
        else:
            self.error_exit('Unknown source %s' % src)

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        lex_flags = self._lex_flags()
        yacc_flags = self._yacc_flags()
        self._generate_lex_yacc_flags(lex_flags, yacc_flags)

        lex_var_name = self._var_name('lex')
        self._generate_cc_source(lex_var_name, self.srcs[0])
        yacc_var_name = self._var_name('yacc')
        self._generate_cc_source(yacc_var_name, self.srcs[1])
        self._write_rule('%s.Depends(%s, %s)' % (
            env_name, lex_var_name, yacc_var_name))

        self._setup_cc_flags()
        self._write_rule('%s.Append(CPPFLAGS="-Wno-unused-function")' % env_name)

        obj_names = []
        obj_name = '%s_object' % self._var_name_of(self.srcs[0])
        self._write_rule('%s = %s.SharedObject(%s)' % (obj_name, env_name, lex_var_name))
        obj_names.append(obj_name)
        obj_name = '%s_object' % self._var_name_of(self.srcs[1])
        self._write_rule('%s = %s.SharedObject(%s[0])' % (obj_name, env_name, yacc_var_name))
        obj_names.append(obj_name)
        self._write_rule('%s = [%s]' % (self._objs_name(), ', '.join(obj_names)))
        self._cc_library()

    def ninja_cc_source(self, source):
        if source.endswith('.l') or source.endswith('.y'):
            return source + '.c'
        elif source.endswith('.ll') or source.endswith('.yy'):
            return source + '.cc'
        else:
            self.error_exit('Unknown source %s' % source)

    def ninja_lex_vars(self):
        lex_flags = self._lex_flags()
        if lex_flags:
            return {'lexflags': ' '.join(lex_flags)}
        return {}

    def ninja_yacc_vars(self):
        yacc_flags = self._yacc_flags()
        if yacc_flags:
            return {'yaccflags': ' '.join(yacc_flags)}
        return {}

    def ninja_lex_rules(self, source, implicit_deps, vars):
        cc = self.ninja_cc_source(source)
        cc_path = self._target_file_path(cc)
        input = self._source_file_path(source)
        self.ninja_build('lex', cc_path, inputs=input, implicit_deps=implicit_deps, variables=vars)
        return cc, cc_path

    def ninja_yacc_rules(self, source, rule, vars):
        cc = self.ninja_cc_source(source)
        cc_path = self._target_file_path(cc)
        input = self._source_file_path(source)
        if cc_path.endswith('.c'):
            h_path = '%s.h' % cc_path[:-2]
        else:
            h_path = '%s.h' % cc_path[:-3]
        self.ninja_build('yacc', cc_path, inputs=input, implicit_outputs=h_path, variables=vars)
        return cc, cc_path, h_path

    def ninja_rules(self):
        lex_file, yacc_file = self.srcs
        yacc_cc, yacc_cc_path, yacc_h_path = self.ninja_yacc_rules(yacc_file, 'yacc',
                                                                   vars=self.ninja_yacc_vars())
        lex_cc, lex_cc_path = self.ninja_lex_rules(lex_file, implicit_deps=[yacc_cc_path],
                                                   vars=self.ninja_lex_vars())
        self.data['generated_hdrs'].append(yacc_h_path)
        self._cc_objects_ninja([lex_cc, yacc_cc], True)
        self._cc_library_ninja()


def lex_yacc_library(name,
                     srcs=[],
                     deps=[],
                     warning='yes',
                     defs=[],
                     incs=[],
                     allow_undefined=False,
                     recursive=False,
                     prefix=None,
                     lexflags=[],
                     yaccflags=[],
                     **kwargs):
    """lex_yacc_library. """
    target = LexYaccLibrary(name,
                            srcs,
                            deps,
                            warning,
                            defs,
                            incs,
                            allow_undefined,
                            recursive,
                            prefix,
                            lexflags,
                            yaccflags,
                            build_manager.instance,
                            kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(lex_yacc_library)
