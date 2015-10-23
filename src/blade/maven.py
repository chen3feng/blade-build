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
import shutil
import subprocess

import configparse
import console


def is_valid_id(id):
    """Check if id is valid. """
    parts = id.split(':')
    if len(parts) == 3:
        group, artifact, version = parts
        if group and artifact and version:
            return True
    return False


class MavenCache(object):
    """MavenCache. Manages maven jar files. """

    __instance = None
    @staticmethod
    def instance():
        if not MavenCache.__instance:
            MavenCache.__instance = MavenCache()
        return MavenCache.__instance

    def __init__(self):
        """Init method. """

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
            console.error_exit('MavenCache was not configured')
        self.__need_check_config = False

    def _check_id(self, id):
        """Check if id is valid. """
        if not is_valid_id(id):
            console.error_exit('Invalid id %s: Id should be group:artifact:version, '
                               'such as jaxen:jaxen:1.1.6' % id)

    def _download_jar(self, id):
        group, artifact, version = id.split(':')
        jar = artifact + '-' + version + '.jar'
        pom = artifact + '-' + version + '.pom'
        log = artifact + '__download.log'
        target_path = self._generate_jar_path(id)
        if not version.endswith('-SNAPSHOT'):
            if (os.path.isfile(os.path.join(target_path, jar)) and
                os.path.isfile(os.path.join(target_path, pom))):
                return True

        console.info('Downloading %s from central repository...' % jar)
        central_repository = ''
        if self.__central_repository:
            central_repository = '-DremoteRepositories=%s' % self.__central_repository

        cmd = ' '.join([self.__maven,
                        'dependency:get',
                        central_repository,
                        '-Dartifact=%s' % id,
                        '> %s' % log])

        cmd = ' '.join([self.__maven,
            'org.apache.maven.plugins:maven-dependency-plugin:2.10:get '
            #'dependency:get '
            '-DgroupId=%s' % group,
            '-DartifactId=%s' % artifact,
            '-Dversion=%s' % version,
            '-Dtype=pom',
            '> %s' % log])
        ret = subprocess.call(cmd, shell=True)
        log_path = os.path.join(target_path, log)
        shutil.move(log, log_path)
        if ret != 0:
            console.warning('Error occurred when downloading %s from central '
                            'repository. Check %s for more details.' % (
                                id, log_path))
            return False
        return True

    def _download_dependency(self, id):
        group, artifact, version = id.split(':')
        target_path = self._generate_jar_path(id)
        classpath = 'classpath.txt'
        if not version.endswith('-SNAPSHOT'):
            if os.path.isfile(os.path.join(target_path, classpath)):
                return True
        console.info('Downloading %s dependencies...' % id)
        target_path = self._generate_jar_path(id)
        pom = os.path.join(target_path, artifact + '-' + version + '.pom')
        log = os.path.join(target_path, artifact + '__classpath.log')
        cmd = ' '.join([self.__maven,
                        'dependency:build-classpath',
                        '-DincludeScope=runtime',
                        '-Dmdep.outputFile=%s' % classpath,
                        '-f %s' % pom,
                        '> %s' % log])
        ret = subprocess.call(cmd, shell=True)
        if ret:
            console.warning('Error occurred when resolving %s dependencies, '
                            ' Check %s for more details.' % (id, log))
            return False
        return True

    def _download_artifact(self, id):
        """Download the specified jar and its transitive dependencies. """
        if not self._download_jar(id):
            return False

        group, artifact, version = id.split(':')
        jar = artifact + '-' + version + '.jar'
        target_path = self._generate_jar_path(id)

        if not self._download_dependency(id):
            self.__jar_database[id] = (os.path.join(target_path, jar), '')
            # Ignore dependency download error
            return True

        classpath = os.path.join(target_path, 'classpath.txt')
        with open(classpath) as f:
            # Read the first line
            self.__jar_database[id] = (os.path.join(target_path, jar), f.readline())

        return True

    def _get_path_from_database(self, id, jar):
        """get_path_from_database. """
        self._check_config()
        self._check_id(id)
        if not id in self.__jar_database:
            success = self._download_artifact(id)
            if not success:
                console.error_exit('Download %s failed' % id)
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

