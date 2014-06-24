# coding=utf-8

import unittest

from frontik.future import Placeholder, FutureStateException


class TestPlaceholder(unittest.TestCase):
    def test_single_data_set(self):
        p = Placeholder()

        p.set_data('first')
        self.assertRaises(FutureStateException, p.set_data, 'second')

    def test_callbacks(self):
        result = 'result'
        p = Placeholder()
        state = {
            'callback1': False,
            'callback2': False,
            'callback3': False,
        }

        def callback1(data):
            state['callback1'] = True
            self.assertEqual(data, result)

        def callback2(data):
            state['callback2'] = True
            self.assertEqual(data, result)

        def callback3(data):
            state['callback3'] = True
            self.assertEqual(data, result)

        p.add_data_callback(callback1)
        p.add_data_callback(callback2)

        self.assertFalse(state['callback1'])
        self.assertFalse(state['callback2'])
        self.assertFalse(state['callback3'])

        p.set_data(result)

        self.assertTrue(state['callback1'])
        self.assertTrue(state['callback2'])
        self.assertFalse(state['callback3'])

        p.add_data_callback(callback3)

        self.assertTrue(state['callback1'])
        self.assertTrue(state['callback2'])
        self.assertTrue(state['callback3'])
