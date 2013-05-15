"""
 Copyright (c) 2013 Tencent Inc.
 All rights reserved.
 Author: Feng chen <phongchen@tencent.com>
"""

import sys
import os.path

zip_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'blade.zip'))
sys.path.append(zip_path)
import blade_main

blade_main.main(zip_path)

