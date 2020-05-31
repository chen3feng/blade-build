# Copyright (c) 2016 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   April 18, 2016

"""

This is the package target module which packages files
into an (compressed) archive.

"""

from __future__ import absolute_import

import os

from blade import build_manager
from blade import build_rules
from blade import console
from blade.blade_util import var_to_list
from blade.target import Target, LOCATION_RE

_package_types = frozenset([
    'tar',
    'tar.gz',
    'tgz',
    'tar.bz2',
    'tbz',
    'zip',
])


class PackageTarget(Target):
    """
    This class is used to pack files into an archive which could be
    compressed using gzip or bz2 according to the package type.
    """

    def __init__(self,
                 name,
                 srcs,
                 deps,
                 visibility,
                 type,
                 out,
                 shell,
                 kwargs):
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        super(PackageTarget, self).__init__(
                name=name,
                type='package',
                srcs=[],
                deps=deps,
                visibility=visibility,
                kwargs=kwargs)

        if type not in _package_types:
            self.error_exit('Invalid type %s. Types supported by the package are %s' % (
                            type, ', '.join(sorted(_package_types))))
        self.data['type'] = type
        self.data['sources'] = []
        self.data['locations'] = []
        self._process_srcs(srcs)

        if not out:
            out = '%s.%s' % (name, type)
        self.data['out'] = out
        self.data['shell'] = shell

    def _process_srcs(self, srcs):
        """
        Process sources which could be regular files, directories or
        location references.
        """
        for s in srcs:
            if isinstance(s, tuple):
                src, dst = s
            elif isinstance(s, str):
                src, dst = s, ''
            else:
                self.error_exit('Invalid src %s. src should be either str or tuple.' % s)

            m = LOCATION_RE.search(src)
            if m:
                self._add_location_reference(m, dst)
            else:
                self._add_package_source(src, dst)

    def _add_location_reference(self, m, dst):
        """Add target location reference. """
        key, type = self._add_location_reference_target(m)
        self.data['locations'].append((key, type, dst))

    def _get_source_path(self, src, dst):
        """
        Return src full path within the workspace and mapping path in the archive.
        """
        if '..' in src or '..' in dst:
            self.error_exit('Invalid src (%s, %s). Relative path is not allowed.' % (src, dst))
        elif src.startswith('//'):
            src = src[2:]
            path = src
        else:
            path = self._source_file_path(src)

        if not dst:
            dst = src
        return path, dst

    def _add_package_source(self, src, dst):
        """Add regular file or directory. """
        src, dst = self._get_source_path(src, dst)
        if not os.path.exists(src):
            self.error_exit('Package source %s does not exist.' % src)
        elif os.path.isfile(src):
            self.data['sources'].append((src, dst))
        else:
            for dir, subdirs, files in os.walk(src):
                # Skip over subdirs starting with '.', such as .svn
                subdirs[:] = [d for d in subdirs if not d.startswith('.')]
                for f in files:
                    f = os.path.join(dir, f)
                    rel_path = os.path.relpath(f, src)
                    self.data['sources'].append((f, os.path.join(dst, rel_path)))

    def ninja_rules(self):
        inputs, entries = [], []
        for src, dst in self.data['sources']:
            inputs.append(src)
            entries.append(dst)

        targets = self.blade.get_build_targets()
        for key, type, dst in self.data['locations']:
            path = targets[key]._get_target_file(type)
            if not path:
                self.warning('Location %s %s is missing. Ignored.' % (key, type))
                continue
            if not dst:
                dst = os.path.basename(path)
            inputs.append(path)
            entries.append(dst)

        output = self._target_file_path(self.data['out'])
        if not self.data['shell']:
            self.ninja_build('package', output, inputs=inputs,
                             variables={'entries': ' '.join(entries)})
        else:
            self.ninja_package_in_shell(output, inputs, entries)

    @staticmethod
    def ninja_rule_from_package_type(t):
        if t == 'zip':
            return 'package_zip'
        return 'package_tar'

    @staticmethod
    def tar_flags(t):
        return {
            'tar': '',
            'tar.gz': '-z',
            'tgz': '-z',
            'tar.bz2': '-j',
            'tbz': '-j',
        }[t]

    def ninja_package_in_shell(self, output, inputs, entries):
        packageroot = self._target_file_path(self.name + '.sources')
        package_sources = []
        for src, dst in zip(inputs, entries):
            dst = os.path.join(packageroot, dst)
            self.ninja_build('copy', dst, inputs=src)
            package_sources.append(dst)
        vars = {
            'entries': ' '.join(entries),
            'packageroot': packageroot,
        }
        type = self.data['type']
        rule = self.ninja_rule_from_package_type(type)
        if type != 'zip':
            vars['tarflags'] = self.tar_flags(type)
        self.ninja_build(rule, output, inputs=package_sources, variables=vars)


def package(name,
            srcs,
            deps=[],
            visibility=None,
            type='tar',
            out=None,
            shell=False,
            **kwargs):
    package_target = PackageTarget(
            name=name,
            srcs=srcs,
            deps=deps,
            visibility=visibility,
            type=type,
            out=out,
            shell=shell,
            kwargs=kwargs)
    build_manager.instance.register_target(package_target)


build_rules.register_function(package)
