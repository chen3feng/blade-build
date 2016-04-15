# Copyright (c) 2016 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   April 14, 2016

"""

This is the fatjar module which packages multiple jar files
into a single fatjar file.

"""

import os
import sys
import zipfile


_JAR_MANIFEST = 'META-INF/MANIFEST.MF'
_FATJAR_EXCLUSIONS = frozenset(['LICENSE', 'README', 'NOTICE',
                                'META-INF/LICENSE', 'META-INF/README',
                                'META-INF/NOTICE', 'META-INF/INDEX.LIST'])


def _is_signature_file(name):
    parts = name.upper().split('/')
    if len(parts) == 2:
        for suffix in ('.SF', '.DSA', '.RSA'):
            if parts[1].endswith(suffix):
                return True
        if parts[1].startswith('SIG-'):
            return True
    return False


def _is_fat_jar_excluded(name):
    name = name.upper()
    for exclusion in _FATJAR_EXCLUSIONS:
        if name.startswith(exclusion):
            return True

    return name == _JAR_MANIFEST or _is_signature_file(name)


def generate_fat_jar(target, jars):
    """Generate a fat jar containing the contents of all the jar dependencies. """
    target_dir = os.path.dirname(target)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    target_fat_jar = zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED)
    # Record paths written in the fat jar to avoid duplicate writing
    zip_path_dict = {}
    zip_path_conflicts, zip_path_logs = 0, []

    for dep_jar in jars:
        jar = zipfile.ZipFile(dep_jar, 'r')
        name_list = jar.namelist()
        for name in name_list:
            if name.endswith('/') or not _is_fat_jar_excluded(name):
                if name not in zip_path_dict:
                    target_fat_jar.writestr(name, jar.read(name))
                    zip_path_dict[name] = os.path.basename(dep_jar)
                else:
                    if not name.endswith('/'):  # Not a directory
                        zip_path_conflicts += 1
                        zip_path_logs.append('%s: duplicate path %s found in {%s, %s}' % (
                                             target, name, zip_path_dict[name],
                                             os.path.basename(dep_jar)))

        jar.close()

    if zip_path_conflicts:
        log = '%s: Found %d conflicts when packaging.' % (target, zip_path_conflicts)
        print >>sys.stdout, log
        print >>sys.stderr, '\n'.join(zip_path_logs)

    # TODO(wentingli): Create manifest from dependency jars later if needed
    contents = 'Manifest-Version: 1.0\nCreated-By: Python.Zipfile (Blade)\n'
    contents += '\n'
    target_fat_jar.writestr(_JAR_MANIFEST, contents)
    target_fat_jar.close()


if __name__ == '__main__':
    generate_fat_jar(sys.argv[1], sys.argv[2:])
