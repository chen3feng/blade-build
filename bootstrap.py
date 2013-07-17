# Copyright (c) 2013 Tencent Inc.
# All rights reserved.
# Author: Feng Chen <phongchen@tencent.com>


"""This is the entry point to load and run blade package.
"""


import sys
import os.path

# Load package from blade.zip or source dir?
# blade_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'blade.zip'))
blade_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'src/blade'))
sys.path.insert(0, blade_path)
import blade_main


blade_main.main(blade_path)

