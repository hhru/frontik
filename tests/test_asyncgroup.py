import unittest
from functools import partial

from frontik.async import AsyncGroup
from frontik.future import Placeholder


class TestAsyncGroup(unittest.TestCase):
    def test_callbacks(self):
        data = []

        def callback2():
            data.append(2)

        def finish_callback():
            self.assertEquals(data, [1, 2])
            data.append(3)

        ag = AsyncGroup(finish_callback)
        cb1 = ag.add(partial(data.append, 1))
        cb2 = ag.add(callback2)

        self.assertEquals(ag._finish_cb_called, False)

        ag.try_finish()

        self.assertEquals(ag._finish_cb_called, False)

        cb1()

        self.assertEquals(ag._finish_cb_called, False)

        cb2()

        self.assertEquals(ag._finish_cb_called, True)
        self.assertEquals(ag._aborted, False)
        self.assertEquals(data, [1, 2, 3])

    def test_notifications(self):
        p = Placeholder()
        ag = AsyncGroup(partial(p.set_data, True))
        not1 = ag.add_notification()
        not2 = ag.add_notification()

        self.assertEquals(ag._finish_cb_called, False)

        not1()

        self.assertEquals(ag._finish_cb_called, False)

        not2('params', are='ignored')

        self.assertEquals(ag._finish_cb_called, True)
        self.assertEquals(ag._aborted, False)
        self.assertEquals(p.get(), True)

    def test_finish(self):
        p = Placeholder()
        ag = AsyncGroup(partial(p.set_data, True))

        self.assertEquals(ag._finish_cb_called, False)

        ag.add_notification()
        ag.finish()

        self.assertEquals(ag._finish_cb_called, True)
        self.assertEquals(ag._aborted, False)
        self.assertEquals(p.get(), True)

    def test_exception_in_first(self):
        log = []

        def callback1():
            raise Exception('callback1 error')

        def callback2():
            self.fail('callback2 should not be called')

        def finish_callback():
            self.fail('finish_callback should not be called')

        ag = AsyncGroup(finish_callback, log=lambda msg, *args: log.append(msg % args), name='test_group')
        cb1 = ag.add(callback1)
        cb2 = ag.add(callback2)

        self.assertRaises(Exception, cb1)
        self.assertEquals(ag._finish_cb_called, False)
        self.assertEquals(ag._aborted, True)

        cb2()

        self.assertEquals(log[-1], 'test_group group: Ignoring response because of already finished group')
        self.assertEquals(ag._finish_cb_called, False)
        self.assertEquals(ag._aborted, True)

    def test_exception_in_last(self):
        log = []

        def callback2():
            raise Exception('callback1 error')

        def finish_callback():
            self.fail('finish_callback should not be called')

        ag = AsyncGroup(finish_callback, log=lambda msg, *args: log.append(msg % args), name='test_group')
        cb1 = ag.add(lambda: None)
        cb2 = ag.add(callback2)

        cb1()

        self.assertRaises(Exception, cb2)

        self.assertEquals(log[-2], 'test_group group: aborting async group due to unhandled exception in callback')
        self.assertEquals(ag._finish_cb_called, False)
        self.assertEquals(ag._aborted, True)

    def test_exception_in_final(self):
        def finish_callback():
            raise Exception('callback1 error')

        ag = AsyncGroup(finish_callback)

        self.assertRaises(Exception, ag.try_finish)
        self.assertEquals(ag._finish_cb_called, True)
        self.assertEquals(ag._aborted, False)
