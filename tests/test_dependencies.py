# coding=utf-8

import unittest

from .instances import frontik_test_app


class TestDependencies(unittest.TestCase):
    def test_dependencies_simple_chain(self):
        response_json = frontik_test_app.get_page_json('dependencies')
        self.assertEqual(
            response_json,
            {
                'run': ['dep1', 'dep2', 'dep3', 'dep4'],
                'post': True
            }
        )
