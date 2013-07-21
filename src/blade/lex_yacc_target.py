# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Feng Chen <phongchen@tencent.com>


"""Define proto_library target
"""


import os
import blade

import console
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
                 recursive,
                 prefix,
                 blade,
                 kwargs):
        """Init method.

        Init the cc lex yacc target

        """
        if len(srcs) != 2:
            raise Exception, ("'srcs' for lex_yacc_library should "
                              "be a pair of (lex_source, yacc_source)")
        CcTarget.__init__(self,
                          name,
                          'lex_yacc_library',
                          srcs,
                          deps,
                          'yes',
                          [], [], [], [], [], [],
                          blade,
                          kwargs)
        self.data['options']['recursive'] = recursive
        self.data['options']['prefix'] = prefix

    def scons_rules(self):
        """scons_rules.

        It outputs the scons rules according to user options.

        """
        self._prepare_to_generate_rule()

        env_name = self._env_name()

        var_name = self._generate_variable_name(self.data['path'], self.data['name'])
        lex_source_file = self._target_file_path(self.data['path'],
                                                 self.data['srcs'][0])
        lex_cc_file = '%s.cc' % lex_source_file

        lex_flags = []
        if self.data.get('options', {}).get('recursive', False):
            lex_flags.append('-R')
        prefix = self.data.get('options', {}).get('prefix', None)
        if prefix:
            lex_flags.append('-P %s' % prefix)
        self._write_rule(
            "lex_%s = %s.CXXFile(LEXFLAGS=%s, target='%s', source='%s');" % (
                var_name, env_name, lex_flags, lex_cc_file, lex_source_file))
        yacc_source_file = os.path.join(self.build_path,
                                        self.data['path'],
                                        self.data['srcs'][1])
        yacc_cc_file = '%s.cc' % yacc_source_file
        yacc_hh_file = '%s.hh' % yacc_source_file

        yacc_flags = []
        if prefix:
            yacc_flags.append('-p %s' % prefix)

        self._write_rule(
            "yacc_%s = %s.Yacc(YACCFLAGS=%s, target=['%s', '%s'], source='%s');" % (
                var_name, env_name, yacc_flags,
                yacc_cc_file, yacc_hh_file, yacc_source_file))
        self._write_rule("%s.Depends(lex_%s, yacc_%s)" % (env_name,
                                                          var_name, var_name))

        self._write_rule(
            "%s = ['%s', '%s']" % (self._objs_name(),
                                   lex_cc_file,
                                   yacc_cc_file))
        self._write_rule("%s = %s.Library('%s', %s)" % (
                var_name,
                env_name,
                self._target_file_path(),
                self._objs_name()))
        self._generate_target_explict_dependency(var_name)

        options = self.blade.get_options()
        if (hasattr(options, 'generate_dynamic') and options.generate_dynamic) or (
            self.data.get('options', {}).get('build_dynamic', False)):
            self._dynamic_cc_library()


def lex_yacc_library(name,
                     srcs=[],
                     deps=[],
                     recursive=False,
                     prefix=None,
                     **kwargs):
    """lex_yacc_library. """
    target = LexYaccLibrary(name,
                            srcs,
                            deps,
                            recursive,
                            prefix,
                            blade.blade,
                            kwargs)
    blade.blade.register_target(target)


build_rules.register_function(lex_yacc_library)

