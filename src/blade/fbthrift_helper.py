# Copyright (c) 2012 iQIYI Inc.
# Copyright (c) 2013 Tencent Inc.
# Copyright (c) 2014 Huahang Liu
#
# All rights reserved.
#
# Author: Jingxu Chen <chenjingxu@qiyi.com>
#         Feng Chen <chen3feng@gmail.com>
#         Huahang Liu <liuhuahang@zerus.co>
#
# Date:   June 28, 2014


"""
 A helper class to get the files generated from thrift IDL files.

 This works with the new thrift compiler and library from Facebook's
 own branch https://github.com/facebook/fbthrift

"""


import os
import re

import console


class FBThriftHelper(object):
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
        files = ['gen-cpp/%s_constants.cpp' % self.thrift_name,
                 'gen-cpp/%s_constants.h' % self.thrift_name,
                 'gen-cpp/%s_reflection.cpp' % self.thrift_name,
                 'gen-cpp/%s_reflection.h' % self.thrift_name,
                 'gen-cpp/%s_types.cpp' % self.thrift_name,
                 'gen-cpp/%s_types.h' % self.thrift_name,
                 'gen-cpp/%s_types.tcc' % self.thrift_name]
        for service in self.services:
            files.append('gen-cpp/%s.cpp' % service)
            files.append('gen-cpp/%s.h' % service)
            files.append('gen-cpp/%s.tcc' % service)
        return files

    def get_generated_cpp2_files(self):
        files = ['gen-cpp2/%s_constants.cpp' % self.thrift_name,
                 'gen-cpp2/%s_constants.h' % self.thrift_name,
                 'gen-cpp2/%s_types.cpp' % self.thrift_name,
                 'gen-cpp2/%s_types.h' % self.thrift_name,
                 'gen-cpp2/%s_types.tcc' % self.thrift_name]
        for service in self.services:
            files.append('gen-cpp2/%s.cpp' % service)
            files.append('gen-cpp2/%s.h' % service)
            files.append('gen-cpp2/%s.tcc' % service)
        return files
