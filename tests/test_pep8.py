# coding=utf-8
from functools import partial
import os.path
import unittest

import pep8

from . import PROJECT_ROOT


class TestPep8(unittest.TestCase):
    CHECKED_PATHS = ('frontik', 'tests', 'examples', 'setup.py', 'frontik-test')

    def test_pep8(self):
        pep8style = pep8.StyleGuide(
            show_pep8=False,
            show_source=True,
            max_line_length=120
        )
        result = pep8style.check_files(map(partial(os.path.join, PROJECT_ROOT), TestPep8.CHECKED_PATHS))
        self.assertEqual(result.total_errors, 0, 'Pep8 found code style errors or warnings')
