#!/usr/bin/env python

"""
Collect the disallowed `maven_jar`s due to the `java_config.maven_jar_allowed_dirs` restriction.
You must run it from the root dir of the workspace.
"""

from __future__ import print_function

import os
import pprint
import re

# Example:
# java/targeting/common/BUILD:3:0: error: scalatra_rl: maven_jar is only allowed under ['thirdparty/java/deps'] and their subdirectories
_PATTERN = re.compile(r'(?P<path>[^:]+):.*: (?P<name>[^ ]+): maven_jar is only allowed under')

def main():
    result = []
    with open('blade-bin/blade.log') as log:
        for line in log:
            match = _PATTERN.match(line)
            if match:
                build = match.group('path')
                name = match.group('name')
                result.append(os.path.dirname(build) + ':' + name)
    pprint.pprint(sorted(result))

if __name__ == '__main__':
    main()
