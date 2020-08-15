#!/usr/bin/env python

"""
Collect the cc_library.hdrs missing reports and generate a suppress list.
You must run it from the root dir of the workspace.
"""

from __future__ import print_function

import os
import pprint
import re

# Example:
# thirdparty/glog/BUILD:3:0: warning: glog: Missing "hdrs" declaration.
_PATTERN = re.compile(r'(?P<path>[^:]+):.*: (?P<name>\w+): Missing "hdrs" declaration')

def main():
    result = []
    with open('blade-bin/blade.log') as log:
        for line in log:
            match = _PATTERN.match(line)
            if match:
                build = match.group('path')
                name = match.group('name')
                result.append(os.path.dirname(build) + ':' + name)
    pprint.pprint(result)

if __name__ == '__main__':
    main()
