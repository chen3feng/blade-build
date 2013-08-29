# Copyright (c) 2012 iQIYI Inc.
# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
#
# Author: Jingxu Chen <chenjingxu@qiyi.com>
#         Feng Chen <chen3feng@gmail.com>
# Date:   October 13, 2012


"""
 A helper class to get the files generated from thrift IDL files.

"""


import os
import re

import console


class ThriftHelper(object):
    def __init__(self, path):
        self.path = path
        if not os.path.isfile(path):
            console.error_exit('%s is not a valid file.' % path)

        self.thrift_name = os.path.basename(path)[0:-7]

        # Package name for each language.
        self.package_name = {}
        # Set to true if there is at least one const definition in the
        # thrift file.
        self.has_constants = False
        self.enums = []
        self.structs = []
        self.exceptions = []
        self.services = []

        # Parse the thrift IDL file.
        self._parse_file()

    def _parse_file(self):
        for line in open(self.path):
            line = line.strip()
            if line.startswith('//') or line.startswith('#'):
                continue
            pos = line.find('//')
            if pos != -1:
                line = line[0:pos]
            pos = line.find('#')
            if pos != -1:
                line = line[0:pos]

            matched = re.match('^namespace ([0-9_a-zA-Z]+) ([0-9_a-zA-Z.]+)', line)
            if matched:
                lang, package = matched.groups()
                self.package_name[lang] = package
                continue

            matched = re.match('(const|struct|service|enum|exception) ([0-9_a-zA-Z]+)', line)
            if not matched:
                continue

            kw, name = matched.groups()
            if kw == 'const':
                self.has_constants = True
            elif kw == 'struct':
                self.structs.append(name)
            elif kw == 'service':
                self.services.append(name)
            elif kw == 'enum':
                self.enums.append(name)
            elif kw == 'exception':
                self.exceptions.append(name)

        if self.has_constants or self.structs or self.enums or \
           self.exceptions or self.services:
            return
        else:
            console.error_exit('%s is an empty thrift file.' % self.path)

    def get_generated_cpp_files(self):
        files = ['%s_constants.cpp' % self.thrift_name,
                 '%s_constants.h' % self.thrift_name,
                 '%s_types.cpp' % self.thrift_name,
                 '%s_types.h' % self.thrift_name]
        for service in self.services:
            files.append('%s.cpp' % service)
            files.append('%s.h' % service)

        return files

    def get_generated_java_files(self):
        java_package = ''
        if 'java' in self.package_name:
            java_package = self.package_name['java']
        base_path = os.path.join(*java_package.split('.'))

        files = []
        if self.has_constants:
            files.append('Constants.java')

        for enum in self.enums:
            files.append('%s.java' % enum)

        for struct in self.structs:
            files.append('%s.java' % struct)

        for exception in self.exceptions:
            files.append('%s.java' % exception)

        for service in self.services:
            files.append('%s.java' % service)

        files = [os.path.join(base_path, f) for f in files]
        return files

    def get_generated_py_files(self):
        py_package = self.thrift_name
        if 'py' in self.package_name:
            py_package = self.package_name['py']
        base_path = os.path.join(*py_package.split('.'))

        files = ['constants.py', 'ttypes.py']
        for service in self.services:
            files.append('%s.py' % service)

        files = [os.path.join(base_path, f) for f in files]
        return files
