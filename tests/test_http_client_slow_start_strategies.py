# coding=utf-8

import unittest

from frontik.http_client import CustomSlowStart


class TestHttpClientSlowStartStrategies(unittest.TestCase):
    def test_custom_strategy_parser_empty(self):
        strategy = CustomSlowStart({})
        self.assertEqual(strategy.intervals, [(0.0, 1.0, 0.0)])

    def test_custom_strategy_parser(self):
        strategy = CustomSlowStart({'custom_slow_start_intervals': '0.2:0.2;0.5:0.2'})
        self.assertEqual(strategy.intervals, [(0.0, 1.0, 0.0), (0.2, 0.0, 0.2), (0.5, 1.6, -0.6)])

    def test_custom_strategy_parser_start_end(self):
        strategy = CustomSlowStart({'custom_slow_start_intervals': '0:0.5;1:0.5'})
        self.assertEqual(strategy.intervals, [(0.0, 0.0, 0.5)])
