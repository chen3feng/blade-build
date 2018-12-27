# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define lex_yacc_library target
"""


import os
import console
import blade

import build_rules
from cc_targets import CcTarget


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
                 blade,
                 kwargs):
        """Init method.

        Init the cc lex yacc target

        """
        if (len(srcs) != 2 or
            (not (srcs[0].endswith('.l') or srcs[0].endswith('.ll'))) or
            (not (srcs[1].endswith('.y') or srcs[1].endswith('.yy')))):
            console.error_exit('%s: srcs for lex_yacc_library should be '
                               'a pair of (lex_source, yacc_source)' % self.fullname)

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
        self.data['allow_undefined'] = allow_undefined
        self.data['link_all_symbols'] = True

    def _generate_header_files(self):
        """Whether this target generates header files during building."""
        return True

    def _setup_lex_yacc_flags(self):
        """Set up lex/yacc flags according to the options. """
        lex_flags, yacc_flags = [], []
        yacc_flags.append('-d')
        if self.data.get('recursive'):
            lex_flags.append('-R')
        prefix = self.data.get('prefix')
        if prefix:
            lex_flags.append('-P %s' % prefix)
            yacc_flags.append('-p %s' % prefix)
        return lex_flags, yacc_flags

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
            console.error_exit('%s: Unknown source %s' % (self.fullname, src))

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()
        env_name = self._env_name()
        lex_flags, yacc_flags = self._setup_lex_yacc_flags()
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
            console.error_exit('%s: Unknown source %s' % (self.fullname, source))

    def ninja_lex_yacc_vars(self):
        lex_vars, yacc_vars = {}, {}
        lex_flags, yacc_flags = self._setup_lex_yacc_flags()
        if lex_flags:
            lex_vars = { 'lexflags' : ' '.join(lex_flags) }
        if yacc_flags:
            yacc_vars = { 'yaccflags' : ' '.join(yacc_flags) }
        return lex_vars, yacc_vars

    def ninja_lex_yacc_rules(self, source, rule, implicit_deps=None, vars=None):
        cc = self.ninja_cc_source(source)
        output = self._target_file_path(cc)
        input = self._source_file_path(source)
        self.ninja_build(output, rule, inputs=input,
                         implicit_deps=implicit_deps, variables=vars)
        return cc, output

    def ninja_rules(self):
        lex, yacc = self.srcs
        lex_vars, yacc_vars = self.ninja_lex_yacc_vars()
        yacc_cc, yacc_cc_path = self.ninja_lex_yacc_rules(yacc, 'yacc', vars=yacc_vars)
        lex_cc, lex_cc_path = self.ninja_lex_yacc_rules(lex, 'lex',
                                                        implicit_deps=[yacc_cc_path],
                                                        vars=lex_vars)
        if yacc_cc.endswith('.c'):
            yacc_hdr = '%s.h' % yacc_cc_path[:-2]
        else:
            yacc_hdr = '%s.h' % yacc_cc_path[:-3]
        self.data['generated_hdrs'].append(yacc_hdr)
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
                            blade.blade,
                            kwargs)
    blade.blade.register_target(target)


build_rules.register_function(lex_yacc_library)
