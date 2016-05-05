# coding=utf-8

import os
from unittest import skipIf

from frontik.compat import PY3

FRONTIK_ROOT = os.path.dirname(os.path.dirname(__file__))

py3_skip = skipIf(PY3, 'test fails on Python 3')


def tearDownModule():
    from .instances import frontik_broken_app, frontik_non_debug, frontik_re_app, frontik_test_app

    frontik_broken_app.stop()
    frontik_non_debug.stop()
    frontik_re_app.stop()
    frontik_test_app.stop()
