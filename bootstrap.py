"""
 Copyright (c) 2013 Tencent Inc.
 All rights reserved.
 Author: Feng chen <phongchen@tencent.com>
"""

import sys
import os.path


def _find_package_path():
    self_path = os.path.dirname(__file__)
    package_path = os.path.join(self_path, 'src/blade')  # Develop mode
    if not os.path.exists(package_path):
        package_path = os.path.join(self_path, 'blade.zip')
    return package_path


package_path = _find_package_path()
sys.path.insert(0, package_path)

import blade_main

blade_main.main(package_path)

