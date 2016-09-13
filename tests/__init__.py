# coding=utf-8

import os
from unittest import skipIf

from frontik.compat import PY3

FRONTIK_ROOT = os.path.dirname(os.path.dirname(__file__))

py3_skip = skipIf(PY3, 'test fails on Python 3')


def tearDownModule():
    from .instances import frontik_broken_app, frontik_no_debug_app, frontik_re_app, frontik_test_app
    from .test_http_client_keep_alive import frontik_keep_alive_app

    frontik_broken_app.stop()
    frontik_no_debug_app.stop()
    frontik_re_app.stop()
    frontik_test_app.stop()
    frontik_keep_alive_app.stop()
