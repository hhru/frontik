# coding=utf-8

import logging
import unittest
from functools import partial

from tornado.concurrent import Future
from tornado.testing import ExpectLog

from frontik.async import async_logger, AsyncGroup


logging.root.setLevel(logging.NOTSET)


class TestAsyncGroup(unittest.TestCase):
    def test_callbacks(self):
        data = []

        def callback2():
            data.append(2)

        def finish_callback():
            self.assertEqual(data, [1, 2])
            data.append(3)

        ag = AsyncGroup(finish_callback)
        cb1 = ag.add(partial(data.append, 1))
        cb2 = ag.add(callback2)

        self.assertEqual(ag._finish_cb_called, False)

        ag.try_finish()

        self.assertEqual(ag._finish_cb_called, False)

        cb1()

        self.assertEqual(ag._finish_cb_called, False)

        cb2()

        self.assertEqual(ag._finish_cb_called, True)
        self.assertEqual(ag._aborted, False)
        self.assertEqual(data, [1, 2, 3])

    def test_notifications(self):
        f = Future()
        ag = AsyncGroup(partial(f.set_result, True))
        not1 = ag.add_notification()
        not2 = ag.add_notification()

        self.assertEqual(ag._finish_cb_called, False)

        not1()

        self.assertEqual(ag._finish_cb_called, False)

        not2('params', are='ignored')

        self.assertEqual(ag._finish_cb_called, True)
        self.assertEqual(ag._aborted, False)
        self.assertEqual(f.result(), True)

    def test_finish(self):
        f = Future()
        ag = AsyncGroup(partial(f.set_result, True))

        self.assertEqual(ag._finish_cb_called, False)

        ag.add_notification()
        ag.finish()

        self.assertEqual(ag._finish_cb_called, True)
        self.assertEqual(ag._aborted, False)
        self.assertEqual(f.result(), True)

    def test_exception_in_first(self):
        def callback1():
            raise Exception('callback1 error')

        def callback2():
            self.fail('callback2 should not be called')

        def finish_callback():
            self.fail('finish_callback should not be called')

        ag = AsyncGroup(finish_callback, name='test_group')
        cb1 = ag.add(callback1)
        cb2 = ag.add(callback2)

        self.assertRaises(Exception, cb1)
        self.assertEqual(ag._finish_cb_called, False)
        self.assertEqual(ag._aborted, True)

        with ExpectLog(async_logger, '.*test_group group: ignoring response because of already finished group'):
            cb2()

        self.assertEqual(ag._finish_cb_called, False)
        self.assertEqual(ag._aborted, True)

    def test_exception_in_last(self):
        def callback2():
            raise Exception('callback1 error')

        def finish_callback():
            self.fail('finish_callback should not be called')

        ag = AsyncGroup(finish_callback, name='test_group')
        cb1 = ag.add(lambda: None)
        cb2 = ag.add(callback2)

        cb1()

        with ExpectLog(async_logger, '.*test_group group: aborting async group due to unhandled exception in callback'):
            self.assertRaises(Exception, cb2)

        self.assertEqual(ag._finish_cb_called, False)
        self.assertEqual(ag._aborted, True)

    def test_exception_in_final(self):
        def finish_callback():
            raise Exception('callback1 error')

        ag = AsyncGroup(finish_callback)

        self.assertRaises(Exception, ag.try_finish)
        self.assertEqual(ag._finish_cb_called, True)
        self.assertEqual(ag._aborted, False)
