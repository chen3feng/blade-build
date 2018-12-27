# Copyright (c) 2016 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   April 18, 2016

"""

This is the package target module which packages files
into an (compressed) archive.

"""

import os

import blade
import build_rules
import console
from blade_util import var_to_list
from blade_util import location_re
from target import Target


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

    This class is derived from Target and used to generate scons
    rules for packaging files into an archive which could be
    compressed using gzip or bz2 according to the package type.

    """
    def __init__(self,
                 name,
                 srcs,
                 deps,
                 type,
                 out,
                 shell,
                 blade,
                 kwargs):
        srcs = var_to_list(srcs)
        deps = var_to_list(deps)

        Target.__init__(self,
                        name,
                        'package',
                        [],
                        deps,
                        None,
                        blade,
                        kwargs)

        if type not in _package_types:
            console.error_exit('%s: Invalid type %s. Types supported '
                               'by the package are %s' % (
                               self.fullname, type, ', '.join(sorted(_package_types))))
        self.data['type'] = type
        self.data['sources'], self.data['locations'] = [], []
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
                console.error_exit('%s: Invalid src %s. src should '
                                   'be either str or tuple.' % (self.fullname, s))

            m = location_re.search(src)
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
            console.error_exit('%s: Invalid src (%s, %s). Relative path is not allowed.'
                               % (self.fullname, src, dst))
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
            console.error_exit('%s: Package source %s does not exist.' % (
                               self.fullname, src))
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

    def _generate_source_rules(self, source_vars, package_path_list, sources_dir):
        env_name = self._env_name()
        for i, source in enumerate(self.data['sources']):
            src, dst = source[0], os.path.join(sources_dir, source[1])
            var = self._var_name('source__%s' % i)
            self._write_rule('%s = %s.PackageSource(target = "%s", source = "%s")' %
                             (var, env_name, dst, src))
            source_vars.append(var)
            package_path_list.append(dst)

    def _generate_location_reference_rules(self, location_vars, sources_dir):
        env_name = self._env_name()
        targets = self.blade.get_build_targets()
        for i, location in enumerate(self.data['locations']):
            key, type, dst = location
            target = targets[key]
            target_var = target._get_target_var(type)
            if not target_var:
                console.warning('%s: Location %s %s is missing. Ignored.' %
                                (self.fullname, key, type))
                continue

            if dst:
                dst = os.path.join(sources_dir, dst)
                var = self._var_name('location__%s' % i)
                self._write_rule('%s = %s.PackageSource(target = "%s", source = %s)' %
                                 (var, env_name, dst, target_var))
                location_vars.append(var)
            else:
                location_vars.append(target_var)

    def scons_rules(self):
        """scons_rules. """
        self._clone_env()
        env_name = self._env_name()
        var_name = self._var_name()

        source_vars, location_vars, package_path_list = [], [], []
        target = self._target_file_path(self.data['out'])
        sources_dir = target + '.sources'
        self._generate_source_rules(source_vars, package_path_list, sources_dir)
        self._generate_location_reference_rules(location_vars, sources_dir)
        self._write_rule('%s = %s.Package(target="%s", source=[%s] + [%s])' % (
                         var_name, env_name, target,
                         ','.join(source_vars), ','.join(sorted(location_vars))))
        package_type = self.data['type']
        self._write_rule('%s.Append(PACKAGESUFFIX="%s")' % (env_name, package_type))

        if package_path_list:
            self._write_rule('%s.Depends(%s, %s.Value(%s))' % (
                env_name, var_name, env_name, package_path_list))
        locations = self.data['locations']
        if locations:
            self._write_rule('%s.Depends(%s, %s.Value("%s"))' % (
                env_name, var_name, env_name, sorted(set(locations))))

    def ninja_rules(self):
        inputs, entries = [], []
        for src, dst in self.data['sources']:
            inputs.append(src)
            entries.append(dst)

        targets = self.blade.get_build_targets()
        for key, type, dst in self.data['locations']:
            path = targets[key]._get_target_file(type)
            if not path:
                console.warning('%s: Location %s %s is missing. Ignored.' %
                                (self.fullname, key, type))
                continue
            if not dst:
                dst = os.path.basename(path)
            inputs.append(path)
            entries.append(dst)

        output = self._target_file_path(self.data['out'])
        if not self.data['shell']:
            self.ninja_build(output, 'package', inputs=inputs,
                             variables={ 'entries' : ' '.join(entries) })
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
        packageroot = self._target_file_path() + '.sources'
        package_sources = []
        for src, dst in zip(inputs, entries):
            dst = os.path.join(packageroot, dst)
            self.ninja_build(dst, 'copy', inputs=src)
            package_sources.append(dst)
        vars = {
            'entries' : ' '.join(entries),
            'packageroot' : packageroot,
        }
        type = self.data['type']
        rule = self.ninja_rule_from_package_type(type)
        if type != 'zip':
            vars['tarflags'] = self.tar_flags(type)
        self.ninja_build(output, rule, inputs=package_sources, variables=vars)


def package(name,
            srcs,
            deps=[],
            type='tar',
            out=None,
            shell=False,
            **kwargs):
    package_target = PackageTarget(name,
                                   srcs,
                                   deps,
                                   type,
                                   out,
                                   shell,
                                   blade.blade,
                                   kwargs)
    blade.blade.register_target(package_target)


build_rules.register_function(package)
