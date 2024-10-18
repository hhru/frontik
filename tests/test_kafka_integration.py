from tests.instances import frontik_test_app


class TestKafkaIntegration:
    def test_kafka(self):
        response_json = frontik_test_app.get_page_json('/kafka')

        assert response_json['metrics_requests']['app'] == 'test_app'
        assert response_json['metrics_requests']['dc'] == 'externalRequest'
        assert 'hostname' in response_json['metrics_requests']
        assert 'requestId' in response_json['metrics_requests']
        assert response_json['metrics_requests']['status'] == 500
        assert 'ts' in response_json['metrics_requests']
        assert 'upstream' in response_json['metrics_requests']
