# coding=utf-8


def tearDownModule():
    from .instances import frontik_broken, frontik_non_debug, frontik_re_app, frontik_test_app
    frontik_broken.stop()
    frontik_non_debug.stop()
    frontik_re_app.stop()
    frontik_test_app.stop()
