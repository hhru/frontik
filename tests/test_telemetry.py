import unittest

from frontik import request_context
from frontik.integrations.telemetry import FrontikIdGenerator, get_netloc


class TestTelemetry(unittest.TestCase):
    def setUp(self):
        self.trace_id_generator = FrontikIdGenerator()

    def test_generate_trace_id_with_none_request_id(self):
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_hex_request_id(self):
        request_context.initialize(None, '163897206709842601f90a070699ac44')
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertEqual('0x163897206709842601f90a070699ac44', hex(trace_id))

    def test_generate_trace_id_with_no_hex_request_id(self):
        request_context.initialize(None, 'non-hex-string-1234')
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_no_str_request_id(self):
        request_context.initialize(None, 12345678910)
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_hex_request_id_and_postfix(self):
        request_context.initialize(None, '163897206709842601f90a070699ac44_some_postfix_string')
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertEqual('0x163897206709842601f90a070699ac44', hex(trace_id))

    def test_generate_trace_id_with_no_hex_request_id_in_first_32_characters(self):
        request_context.initialize(None, '16389720670_NOT_HEX_9842601f90a070699ac44_some_postfix_string')
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)
        self.assertNotEqual('0x16389720670_NOT_HEX_9842601f90a0', hex(trace_id))

    def test_generate_trace_id_with_request_id_len_less_32_characters(self):
        request_context.initialize(None, '163897206')
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)
        self.assertNotEqual('0x163897206', hex(trace_id))

    def test_get_netloc(self):
        self.assertEqual('balancer:7000', get_netloc('balancer:7000/xml/get-article/'))
        self.assertEqual('balancer:7000', get_netloc('//balancer:7000/xml/get-article/'))
        self.assertEqual('balancer:7000', get_netloc('https://balancer:7000/xml/get-article/'))
        self.assertEqual('hh.ru', get_netloc('https://hh.ru'))
        self.assertEqual('ftp:', get_netloc('ftp://hh.ru'))
