"""
 Copyright (c) 2013 Tencent Inc.
 All rights reserved.
 Author: Feng Chen <phongchen@tencent.com>
"""

import sys
import os.path

#zip_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'blade.zip'))
zip_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/blade'))
sys.path.insert(0, zip_path)
import blade_main

blade_main.main(zip_path)

