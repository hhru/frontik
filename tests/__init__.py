# coding=utf-8


def tearDownModule():
    from .instances import frontik_debug, frontik_non_debug
    frontik_debug.stop()
    frontik_non_debug.stop()
