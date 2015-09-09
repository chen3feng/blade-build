# Copyright (c) 2015 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   August 28, 2015

"""

This is the maven module which manages jar files downloaded
from maven repository

"""

import os
import subprocess

import configparse
import console

maven = None

class Maven(object):
    """Maven. Manages maven jar files. """
    def __init__(self, blade_root_path):
        """Init method. """
        self.__root_dir = blade_root_path

        # jar database
        #   key: jar id in the format group:artifact:version
        #   value: tuple
        #     tuple[0]: jar path
        #     tuple[1]: jar dependencies paths separated by colon,
        #               including transitive dependencies
        self.__jar_database = {}

        java_config = configparse.blade_config.get_config('java_config')
        self.__maven = java_config.get('maven')
        self.__central_repository = java_config.get('maven_central')
        # Local repository is set to the maven default directory
        # and could not be configured currently
        local_repository = '~/.m2/repository'
        self.__local_repository = os.path.expanduser(local_repository)
        self.__need_check_config = True

    def _generate_jar_path(self, id):
        """Generate jar path within local repository. """
        group, artifact, version = id.split(':')
        return os.path.join(self.__local_repository,
                            group.replace('.', '/'), artifact, version)

    def _check_config(self):
        """Check whether maven is configured correctly. """
        if not self.__need_check_config:
            return
        if not self.__maven:
            console.error_exit('Maven was not configured')
        if not self.__central_repository:
            console.error_exit('Maven repository was not configured')
        self.__maven = os.path.join(self.__root_dir, self.__maven) 
        if not os.path.exists(self.__maven):
            console.error_exit('Maven was not found')
        self.__need_check_config = False

    def _check_id(self, id):
        """Check if id is valid. """
        parts = id.split(':')
        if len(parts) == 3:
            group, artifact, version = parts
            if group and artifact and version:
                return
        console.error_exit('Invalid id %s: Id should be group:artifact:version, '
                           'such as jaxen:jaxen:1.1.6' % id)

    def _download_jar(self, id):
        """Download the specified jar and its transitive dependencies. """
        group, artifact, version = id.split(':')
        artifact = artifact + '-' + version 
        jar = artifact + '.jar'
        pom = artifact + '.pom'
        log = artifact + '__download.log'
        cmd = ' '.join([self.__maven,
                        'dependency:get',
                        '-DremoteRepositories=%s' % self.__central_repository,
                        '-Dartifact=%s' % id,
                        '> %s' % log])
        console.info('Downloading %s from central repository...' % jar)
        ret = subprocess.call(cmd, shell=True)
        if ret:
            console.warning('Error occurred when downloading %s from central '
                            'repository. Check %s for more details.' % (jar, log))
            return False
        path = self._generate_jar_path(id)
        os.rename(log, os.path.join(path, log))

        classpath = 'classpath.txt'
        log = artifact + '__classpath.log'
        cmd = ' '.join([self.__maven,
                        'dependency:build-classpath',
                        '-Dmdep.outputFile=%s' % classpath,
                        '-f %s' % os.path.join(path, pom),
                        '> %s' % os.path.join(path, log)])
        console.info('Resolving %s dependencies...' % jar)
        ret = subprocess.call(cmd, shell=True)
        if ret:
            console.warning('Error occurred when resolving %s dependencies' % jar)
            return False
        classpath = os.path.join(path, classpath)
        with open(classpath) as f:
            # Read the first line
            self.__jar_database[id] = (os.path.join(path, jar), f.readline())

        return True

    def _get_path_from_database(self, id, jar):
        """get_path_from_database. """
        self._check_config()
        self._check_id(id)
        if not id in self.__jar_database:
            success = self._download_jar(id)
            if not success:
                return '';
        if jar:
            return self.__jar_database[id][0]
        else:
            return self.__jar_database[id][1]
        
    def get_jar_path(self, id):
        """get_jar_path

        Return local jar path corresponding to the id specified in the
        format group:artifact:version.
        Download jar files and its transitive dependencies if needed.

        """
        return self._get_path_from_database(id, True)

    def get_jar_deps_path(self, id):
        """get_jar_deps_path

        Return a string of the dependencies path separated by colon.
        This string can be used in java -cp later.

        """
        return self._get_path_from_database(id, False)

