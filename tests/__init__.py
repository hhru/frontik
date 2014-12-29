# coding=utf-8
import os.path

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))


def tearDownModule():
    from .instances import frontik_broken_app, frontik_non_debug, frontik_re_app, frontik_test_app
    frontik_broken_app.stop()
    frontik_non_debug.stop()
    frontik_re_app.stop()
    frontik_test_app.stop()
