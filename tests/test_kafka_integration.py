import pytest

try:
    has_kafka = True
except Exception:
    has_kafka = False

from tests.instances import frontik_test_app


@pytest.mark.skipif(not has_kafka, reason='aiokafka library not found')
class TestKafkaIntegration:
    def test_kafka(self):
        response_json = frontik_test_app.get_page_json('kafka')

        assert response_json['metrics_requests']['app'] == 'tests.projects.test_app'
        assert response_json['metrics_requests']['dc'] == 'externalRequest'
        assert 'hostname' in response_json['metrics_requests']
        assert 'requestId' in response_json['metrics_requests']
        assert response_json['metrics_requests']['status'] == 500
        assert 'ts' in response_json['metrics_requests']
        assert 'upstream' in response_json['metrics_requests']
