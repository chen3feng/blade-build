# Copyright (c) 2015 Tencent Inc.
# All rights reserved.
#
# Author: Li Wenting <wentingli@tencent.com>
# Date:   August 28, 2015

"""

This is the maven module which manages jar files downloaded
from maven repository

"""

from __future__ import absolute_import

import os
import shutil
import subprocess
import time

from blade import config
from blade import console


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

        java_config = config.get_section('java_config')
        self.__maven = java_config.get('maven')
        self.__central_repository = java_config.get('maven_central')
        self._check_config()

        self.__snapshot_update_policy = java_config.get('maven_snapshot_update_policy')
        if self.__snapshot_update_policy == 'interval':
            interval = java_config.get('maven_snapshot_update_interval')
            if not interval:
                Console.error_exit('java_config: "maven_snapshot_update_interval" is required when '
                                   '"maven_snapshot_update_policy" is "interval"')
            self.__snapshot_update_interval = interval * 60  # minutes
        else:
            self.__snapshot_update_interval = 86400

        # Local repository is set to the maven default directory
        # and could not be configured currently
        local_repository = '~/.m2/repository'
        self.__local_repository = os.path.expanduser(local_repository)

        # Download the snapshot artifact daily
        self.__build_time = time.time()

    def _generate_jar_path(self, id):
        """Generate jar path within local repository. """
        group, artifact, version = id.split(':')
        return os.path.join(self.__local_repository,
                            group.replace('.', '/'), artifact, version)

    def _check_config(self):
        """Check whether maven is configured correctly. """
        if not self.__maven:
            console.error_exit('MavenCache is not configured')

    def _is_file_expired(self, filename):
        """Check if the modification time of file is expired relative to build time. """
        return self.__build_time - os.path.getmtime(filename) > self.__snapshot_update_interval

    def _need_download(self, filename, version, logfile):
        if not os.path.isfile(os.path.join(filename)):
            return True
        if not version.endswith('-SNAPSHOT'):
            return False
        if self.__snapshot_update_policy == 'always':
            return True
        if self.__snapshot_update_policy == 'never':
            return False
        if not os.path.isfile(logfile):
            return True
        # Use the logfile's timestamp as the update time
        return self._is_file_expired(logfile)

    def _filename_base(self, artifact, version, classifier):
        if classifier:
            return artifact + '-' + version + '-' + classifier
        return artifact + '-' + version

    def _download_jar(self, id, classifier, target):
        group, artifact, version = id.split(':')
        basename = self._filename_base(artifact, version, classifier)
        pom = basename + '.pom'
        jar = basename + '.jar'

        # Write log to build dir temporarily, and move it into the target_path after success.
        log_path = os.path.join(self.__log_dir, basename + '_download.log')
        target_path = self._generate_jar_path(id)
        target_log = 'download.log'
        if classifier:
            target_log = classifier + '_download.log'
        target_log = os.path.join(target_path, target_log)

        if not self._need_download(os.path.join(target_path, jar), version, target_log):
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
        cmd += ' -e -X'  # More detailed debug message
        if subprocess.call('%s > %s' % (cmd, log_path), shell=True) != 0:
            console.warning('//%s: Error occurred when downloading %s from central '
                            'repository. Check %s for details.' % (target, id, log_path))
            cmd += ' -Dtransitive=false'
            if subprocess.call('%s > %s' % (cmd, log_path + '.transitive'), shell=True) != 0:
                return False
            console.warning('//%s: Download standalone artifact %s successfully, but '
                            'its transitive dependencies are unavailable.' % (target, id))
        shutil.move(log_path, target_log)
        return True

    def _download_dependency(self, id, classifier, target):
        group, artifact, version = id.split(':')
        target_path = self._generate_jar_path(id)
        classpath = 'classpath.txt'
        log = 'classpath.log'
        log = os.path.join(target_path, log)
        if not self._need_download(os.path.join(target_path, classpath), version, log):
            return True

        # if classifier:
        #     id = '%s:%s' % (id, classifier)
        #     # Currently analyzing dependencies of classifier jar
        #     # usually fails. Here when there is no classpath.txt
        #     # file but classpath.log exists, that means the failure
        #     # of analyzing dependencies last time
        #     if (not os.path.exists(os.path.join(target_path, classpath))
        #         and os.path.exists(log)):
        #         return False

        console.info('Downloading %s dependencies...' % id)
        pom = os.path.join(target_path, artifact + '-' + version + '.pom')
        cmd = ' '.join([self.__maven,
                        'dependency:build-classpath',
                        '-DincludeScope=runtime',
                        '-Dmdep.outputFile=%s' % classpath])
        cmd += ' -e -X -f %s > %s' % (pom, log)
        if subprocess.call(cmd, shell=True) != 0:
            console.warning('//%s: Error occurred when resolving %s dependencies. '
                            'Check %s for details.' % (target, id, log))
            return False
        return True

    def _download_artifact(self, id, classifier, target):
        """Download the specified jar and its transitive dependencies. """
        if not self._download_jar(id, classifier, target):
            return False

        group, artifact, version = id.split(':')
        path = self._generate_jar_path(id)
        jar = artifact + '-' + version + '.jar'
        if classifier:
            jar = artifact + '-' + version + '-' + classifier + '.jar'
        self.__jar_database[(id, classifier)] = MavenArtifact(os.path.join(path, jar))
        return True

    def _get_artifact_from_database(self, id, classifier, target):
        """get_artifact_from_database. """
        if (id, classifier) not in self.__jar_database:
            if not self._download_artifact(id, classifier, target):
                console.error_exit('//%s: Download %s failed' % (target, id))
        return self.__jar_database[(id, classifier)]

    def get_jar_path(self, id, classifier, target):
        """get_jar_path

        Return local jar path corresponding to the id specified in the
        format group:artifact:version.
        Download jar files and its transitive dependencies if needed.

        """
        artifact = self._get_artifact_from_database(id, classifier, target)
        return artifact.path

    def get_jar_deps_path(self, id, classifier, target):
        """get_jar_deps_path

        Return a string of the dependencies path separated by colon.
        This string can be used in java -cp later.

        """
        artifact = self._get_artifact_from_database(id, classifier, target)
        if artifact.deps is None:
            if not self._download_dependency(id, classifier, target):
                # Ignore dependency download error
                artifact.deps = ''
            else:
                path = self._generate_jar_path(id)
                classpath = os.path.join(path, 'classpath.txt')
                with open(classpath) as f:
                    # Read the first line
                    artifact.deps = f.readline()
        return artifact.deps
