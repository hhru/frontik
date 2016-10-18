# coding=utf-8

import os

FRONTIK_ROOT = os.path.dirname(os.path.dirname(__file__))


def tearDownModule():
    from .instances import frontik_broken_app, frontik_no_debug_app, frontik_re_app, frontik_test_app

    frontik_broken_app.stop()
    frontik_no_debug_app.stop()
    frontik_re_app.stop()
    frontik_test_app.stop()
