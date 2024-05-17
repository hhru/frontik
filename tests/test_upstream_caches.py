from http_client import options as http_client_options

from frontik.integrations.statsd import StatsDClientStub
from frontik.options import options
from frontik.service_discovery import UpstreamManager


class TestUpstreamCaches:
    @classmethod
    def setup_class(cls):
        options.consul_enabled = False

    @classmethod
    def teardown_class(cls):
        options.consul_enabled = True

    def test_update_upstreams_servers_different_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['Test', 'AnoTher']
        value_one_dc = [
            {
                'Node': {'ID': '1', 'Node': '', 'Address': '1.1.1.1', 'Datacenter': 'test'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        value_another_dc = [
            {
                'Node': {'ID': '2', 'Node': '', 'Address': '2.2.2.2', 'Datacenter': 'another'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        upstream_cache = UpstreamManager({}, StatsDClientStub(), None, None, False, 'test')
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)

        assert len(upstream_cache._upstreams_servers) == 2
        assert len(upstream_cache._upstreams['app'].servers) == 2

    def test_update_upstreams_servers_same_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
        value_one_dc = [
            {
                'Node': {'ID': '1', 'Node': '', 'Address': '1.1.1.1', 'Datacenter': 'test'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        upstream_cache = UpstreamManager({}, StatsDClientStub(), None, None, False, 'test')
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_one_dc)

        assert len(upstream_cache._upstreams_servers) == 1
        assert len(upstream_cache._upstreams['app'].servers) == 1

    def test_multiple_update_upstreams_servers_different_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
        value_one_dc = [
            {
                'Node': {'ID': '1', 'Node': '', 'Address': '1.1.1.1', 'Datacenter': 'test'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        value_another_dc = [
            {
                'Node': {'ID': '2', 'Node': '', 'Address': '2.2.2.2', 'Datacenter': 'another'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        upstream_cache = UpstreamManager({}, StatsDClientStub(), None, None, False, 'test')
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)
        upstream_cache._update_upstreams_service('app', value_one_dc)

        assert len(upstream_cache._upstreams_servers) == 2
        assert len(upstream_cache._upstreams['app'].servers) == 2

    def test_remove_upstreams_servers_different_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
        value_test_dc = [
            {
                'Node': {'ID': '1', 'Node': '', 'Address': '1.1.1.1', 'Datacenter': 'test'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        value_another_dc = [
            {
                'Node': {'ID': '2', 'Node': '', 'Address': '2.2.2.2', 'Datacenter': 'another'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
            {
                'Node': {'ID': '2', 'Node': '', 'Address': '2.2.2.2', 'Datacenter': 'another'},
                'Service': {
                    'ID': '3',
                    'Service': 'app',
                    'Address': '',
                    'Port': 999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        value_another_remove_service_dc = [
            {
                'Node': {'ID': '2', 'Node': '', 'Address': '2.2.2.2', 'Datacenter': 'another'},
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {'Passing': 100, 'Warning': 0},
                },
            },
        ]

        upstream_cache = UpstreamManager({}, StatsDClientStub(), None, None, False, 'test')
        upstream_cache._update_upstreams_service('app', value_test_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)

        assert len(upstream_cache._upstreams_servers['app-test']) == 1
        assert len(upstream_cache._upstreams_servers['app-another']) == 2
        assert len(upstream_cache._upstreams['app'].servers) == 3

        upstream_cache._update_upstreams_service('app', value_another_remove_service_dc)

        assert len(upstream_cache._upstreams_servers['app-another']) == 1
        assert upstream_cache._upstreams_servers['app-another'][0].address == '2.2.2.2:9999'
        assert len(upstream_cache._upstreams['app'].servers) == 3
        assert len([server for server in upstream_cache._upstreams['app'].servers if server is not None]) == 2
