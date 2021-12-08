import unittest

from frontik import request_context
from frontik.telemetry import FrontikIdGenerator


class TelemetryTestCase(unittest.TestCase):
    def setUp(self):
        self.trace_id_generator = FrontikIdGenerator()

    def test_generate_trace_id_with_none_request_id(self):
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_hex_request_id(self):
        request_context.initialize(None, '1234567890abcdef')
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertEqual('0x1234567890abcdef', hex(trace_id))

    def test_generate_trace_id_with_no_hex_request_id(self):
        request_context.initialize(None, 'non-hex-string-1234')
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)

    def test_generate_trace_id_with_no_str_request_id(self):
        request_context.initialize(None, 12345678910)
        trace_id = self.trace_id_generator.generate_trace_id()
        self.assertIsNotNone(trace_id)
