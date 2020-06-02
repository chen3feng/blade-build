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
    """This class generates lex yacc rules."""

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 warning,
                 defs,
                 incs,
                 allow_undefined,
                 recursive,
                 prefix,
                 lexflags,
                 yaccflags,
                 kwargs):
        """Init method.

        Init the cc lex yacc target

        """
        if (len(srcs) != 2 or
                (not (srcs[0].endswith('.l') or srcs[0].endswith('.ll'))) or
                (not (srcs[1].endswith('.y') or srcs[1].endswith('.yy')))):
            self.error_exit('"lex_yacc_library.srcs"  must be a pair of [lex_file, yacc_file]')

        super(LexYaccLibrary, self).__init__(
                name=name,
                type='lex_yacc_library',
                srcs=srcs,
                deps=deps,
                visibility=visibility,
                warning=warning,
                defs=defs,
                incs=incs,
                export_incs=[],
                optimize=None,
                extra_cppflags=[],
                extra_linkflags=[],
                kwargs=kwargs)

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


def lex_yacc_library(
        name,
        srcs=[],
        deps=[],
        visibility=None,
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
    target = LexYaccLibrary(
            name=name,
            srcs=srcs,
            deps=deps,
            warning=warning,
            visibility=visibility,
            defs=defs,
            incs=incs,
            allow_undefined=allow_undefined,
            recursive=recursive,
            prefix=prefix,
            lexflags=lexflags,
            yaccflags=yaccflags,
            kwargs=kwargs)
    build_manager.instance.register_target(target)


build_rules.register_function(lex_yacc_library)
