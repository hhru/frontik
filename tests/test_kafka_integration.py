import unittest

try:
    import aiokafka

    has_kafka = True
except Exception:
    has_kafka = False

from tests.instances import frontik_test_app


@unittest.skipIf(not has_kafka, 'aiokafka library not found')
class TestKafkaIntegration(unittest.TestCase):
    def test_kafka(self):
        response_json = frontik_test_app.get_page_json('kafka')

        self.assertEqual(response_json['metrics_requests']['app'], 'tests.projects.test_app')
        self.assertEqual(response_json['metrics_requests']['dc'], 'externalRequest')
        self.assertTrue('hostname' in response_json['metrics_requests'])
        self.assertTrue('requestId' in response_json['metrics_requests'])
        self.assertEqual(response_json['metrics_requests']['status'], 500)
        self.assertTrue('ts' in response_json['metrics_requests'])
        self.assertTrue('upstream' in response_json['metrics_requests'])
