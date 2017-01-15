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
import time

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


class MavenArtifact(object):
    """
    MavenArtifact represents a jar artifact and its transitive dependencies
    separated by colon in maven cache.
    """
    def __init__(self, path):
        self.path = path
        self.deps = None


class MavenCache(object):
    """MavenCache. Manages maven jar files. """

    __instance = None
    @staticmethod
    def instance(log_dir):
        if not MavenCache.__instance:
            MavenCache.__instance = MavenCache(log_dir)
        return MavenCache.__instance

    def __init__(self, log_dir):
        """Init method. """

        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.__log_dir = log_dir
        #   key: (id, classifier)
        #     id: jar id in the format group:artifact:version
        #   value: an instance of MavenArtifact
        self.__jar_database = {}

        java_config = configparse.blade_config.get_config('java_config')
        self.__maven = java_config.get('maven')
        self.__central_repository = java_config.get('maven_central')
        # Local repository is set to the maven default directory
        # and could not be configured currently
        local_repository = '~/.m2/repository'
        self.__local_repository = os.path.expanduser(local_repository)
        self.__need_check_config = True

        # Download the snapshot artifact daily
        self.__build_time = time.time()
        self.__one_day_interval = 86400

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

    def _is_log_expired(self, log):
        """Check if the modification time of log file is expired relative to build time. """
        return self.__build_time - os.path.getmtime(log) > self.__one_day_interval

    def _download_jar(self, id, classifier):
        group, artifact, version = id.split(':')
        pom = artifact + '-' + version + '.pom'
        jar = artifact + '-' + version + '.jar'
        log = artifact + '__download.log'
        if classifier:
            jar = artifact + '-' + version + '-' + classifier + '.jar'
            log = artifact + '-' + classifier + '__download.log'
        log_path = os.path.join(self.__log_dir, log)
        target_path = self._generate_jar_path(id)
        target_log = os.path.join(target_path, log)
        if (os.path.isfile(os.path.join(target_path, jar)) and
            os.path.isfile(os.path.join(target_path, pom))):
            if not version.endswith('-SNAPSHOT'):
                return True
            if os.path.isfile(target_log) and not self._is_log_expired(target_log):
                return True

        if classifier:
            id = '%s:%s' % (id, classifier)
        console.info('Downloading %s from central repository...' % id)
        cmd = ' '.join([self.__maven,
                        'dependency:get',
                        '-DgroupId=%s' % group,
                        '-DartifactId=%s' % artifact,
                        '-Dversion=%s' % version])
        if classifier:
            cmd += ' -Dclassifier=%s' % classifier
        if subprocess.call('%s > %s' % (cmd, log_path), shell=True):
            console.warning('Error occurred when downloading %s from central '
                            'repository. Check %s for more details.' % (
                            id, log_path))
            cmd += ' -Dtransitive=false'
            if subprocess.call('%s > %s' % (cmd, log_path + '.transitive'),
                               shell=True):
                return False
            console.warning('Download standalone artifact %s successfully, but '
                            'its transitive dependencies are unavailable.' % id)
        shutil.copy(log_path, target_log)
        return True

    def _download_dependency(self, id, classifier):
        group, artifact, version = id.split(':')
        target_path = self._generate_jar_path(id)
        log, classpath = artifact + '__classpath.log', 'classpath.txt'
        if classifier:
            log = artifact + '-' + classifier + '__classpath.log'
            classpath = 'classpath-%s.txt' % classifier
        log = os.path.join(target_path, log)
        if os.path.isfile(os.path.join(target_path, classpath)):
            if not version.endswith('-SNAPSHOT'):
                return True
            if os.path.isfile(log) and not self._is_log_expired(log):
                return True

        if classifier:
            id = '%s:%s' % (id, classifier)
            # Currently analyzing dependencies of classifier jar
            # usually fails. Here when there is no classpath.txt
            # file but classpath.log exists, that means the failure
            # of analyzing dependencies last time
            if (not os.path.exists(os.path.join(target_path, classpath))
                and os.path.exists(log)):
                return False

        console.info('Downloading %s dependencies...' % id)
        pom = os.path.join(target_path, artifact + '-' + version + '.pom')
        cmd = ' '.join([self.__maven,
                        'dependency:build-classpath',
                        '-DincludeScope=runtime',
                        '-Dmdep.outputFile=%s' % classpath])
        if classifier:
            cmd += ' -Dclassifier=%s' % classifier
        cmd += ' -f %s > %s' % (pom, log)
        if subprocess.call(cmd, shell=True):
            console.warning('Error occurred when resolving %s dependencies. '
                            'Check %s for more details.' % (id, log))
            return False
        return True

    def _download_artifact(self, id, classifier):
        """Download the specified jar and its transitive dependencies. """
        if not self._download_jar(id, classifier):
            return False

        group, artifact, version = id.split(':')
        path = self._generate_jar_path(id)
        jar = artifact + '-' + version + '.jar'
        if classifier:
            jar = artifact + '-' + version + '-' + classifier + '.jar'
        self.__jar_database[(id, classifier)] = MavenArtifact(os.path.join(path, jar))
        return True

    def _get_artifact_from_database(self, id, classifier):
        """get_artifact_from_database. """
        self._check_config()
        self._check_id(id)
        if (id, classifier) not in self.__jar_database:
            if not self._download_artifact(id, classifier):
                console.error_exit('Download %s failed' % id)
        return self.__jar_database[(id, classifier)]

    def get_jar_path(self, id, classifier):
        """get_jar_path

        Return local jar path corresponding to the id specified in the
        format group:artifact:version.
        Download jar files and its transitive dependencies if needed.

        """
        artifact = self._get_artifact_from_database(id, classifier)
        return artifact.path

    def get_jar_deps_path(self, id, classifier):
        """get_jar_deps_path

        Return a string of the dependencies path separated by colon.
        This string can be used in java -cp later.

        """
        artifact = self._get_artifact_from_database(id, classifier)
        if artifact.deps is None:
            if not self._download_dependency(id, classifier):
                # Ignore dependency download error
                artifact.deps = ''
            else:
                path = self._generate_jar_path(id)
                classpath = os.path.join(path, 'classpath.txt')
                if classifier:
                    classpath = os.path.join(path, 'classpath-%s.txt' % classifier)
                with open(classpath) as f:
                    # Read the first line
                    artifact.deps = f.readline()
        return artifact.deps
