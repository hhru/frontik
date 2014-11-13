# coding=utf-8

import unittest

from frontik.future import Future, FutureStateException

from .instances import frontik_test_app


class TestPlaceholder(unittest.TestCase):
    def test_single_data_set(self):
        f = Future()

        f.set_result('first')
        self.assertRaises(FutureStateException, f.set_result, 'second')

    def test_callbacks(self):
        result = 'result'
        f = Future()
        state = {
            'callback1': False,
            'callback2': False,
            'callback3': False,
        }

        def callback1(future):
            state['callback1'] = True
            self.assertEqual(future.result(), result)

        def callback2(future):
            state['callback2'] = True
            self.assertEqual(future.result(), result)

        def callback3(future):
            state['callback3'] = True
            self.assertEqual(future.result(), result)

        f.add_done_callback(callback1)
        f.add_done_callback(callback2)

        self.assertFalse(state['callback1'])
        self.assertFalse(state['callback2'])
        self.assertFalse(state['callback3'])

        f.set_result(result)

        self.assertTrue(state['callback1'])
        self.assertTrue(state['callback2'])
        self.assertFalse(state['callback3'])

        f.add_done_callback(callback3)

        self.assertTrue(state['callback1'])
        self.assertTrue(state['callback2'])
        self.assertTrue(state['callback3'])

    def test_future_with_main_asyncgroup(self):
        response = frontik_test_app.get_page('future')
        self.assertEqual(response.content, '{"1": "yay", "cb": "yes", "2": "yay"}')
