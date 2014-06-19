# coding=utf-8

import sys
import unittest
from functools import partial

from frontik import magic_imp


class TestImporter(unittest.TestCase):
    def test_simple(self):
        importer = magic_imp.FrontikAppImporter('test_app', 'tests/projects/test_app')
        a = importer.imp_app_module('simple_lib_use')

        self.assertEquals(a.a, 10)

    def test_import_syntax_error(self):
        importer = magic_imp.FrontikAppImporter('test_app', 'tests/projects/test_app')
        self.assertRaises(Exception, partial(importer.imp_app_module, 'syntax_error'))
        self.assertNotIn('frontik.imp.test_app.syntax_error', sys.modules)
