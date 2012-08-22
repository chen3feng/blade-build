"""

 Copyright (c) 2011 Tencent Inc.
 All rights reserved.

 Author: Michaelpeng <michaelpeng@tencent.com>
 Date:   October 20, 2011

 This is the main test module for all targets.

"""


import os
import sys
sys.path.append('..')
import unittest
from cc_binary_test import TestCcBinary
from cc_library_test import TestCcLibrary
from cc_plugin_test import TestCcPlugin
from cc_test_test import TestCcTest
from gen_rule_test import TestGenRule
from html_test_runner import HTMLTestRunner
from java_jar_test import TestJavaJar
from lex_yacc_test import TestLexYacc
from load_builds_test import TestLoadBuilds
from proto_library_test import TestProtoLibrary
from prebuild_cc_library_test import TestPrebuildCcLibrary
from query_target_test import TestQuery
from resource_library_test import TestResourceLibrary
from swig_library_test import TestSwigLibrary
from target_dependency_test import TestDepsAnalyzing
from test_target_test import TestTestRunner


def _main():
    """main method. """
    generate_html = False
    if len(sys.argv) > 1 and sys.argv[1].startswith('html'):
        generate_html = True
    suite_test = unittest.TestSuite()
    suite_test.addTests(
            [
                unittest.defaultTestLoader.loadTestsFromTestCase(TestCcLibrary),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestCcBinary),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestCcPlugin),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestCcTest),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestGenRule),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestJavaJar),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestLexYacc),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestLoadBuilds),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestProtoLibrary),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestResourceLibrary),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestSwigLibrary),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestDepsAnalyzing),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestQuery),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestTestRunner),
                unittest.defaultTestLoader.loadTestsFromTestCase(TestPrebuildCcLibrary)
            ])

    if generate_html:
        runner = HTMLTestRunner(title="Blade unit test report")
        runner.run(suite_test)
    else:
        runner = unittest.TextTestRunner()
        runner.run(suite_test)

if __name__ == "__main__":
    _main()
