# coding=utf-8

from tests.instances import frontik_debug, frontik_non_debug


def tearDownModule():
    frontik_debug.stop()
    frontik_non_debug.stop()
