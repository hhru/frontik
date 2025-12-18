from threading import Lock
from typing import Callable, Optional

from http_client import options as http_client_options

from frontik.options import Options, options
from frontik.service_discovery import MasterServiceDiscovery


class StubServiceDiscovery(MasterServiceDiscovery):
    def __init__(self, test_options: Options) -> None:
        self.options = test_options

        self._upstreams_config: dict = {}
        self._upstreams_servers: dict = {}

        self._upstreams = {}
        self._upstreams_lock = Lock()
        self._send_to_all_workers: Optional[Callable] = None


class TestUpstreamCaches:
    def test_update_upstreams_servers_different_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['Test', 'AnoTher']
        options.datacenters = ['Test', 'AnoTher']
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

        service_discovery = StubServiceDiscovery(options)
        service_discovery._update_upstreams_service('app', value_one_dc)
        service_discovery._update_upstreams_service('app', value_another_dc)

        assert len(service_discovery._upstreams_servers) == 2
        assert len(service_discovery.get_upstream('app').servers) == 2

    def test_update_upstreams_servers_same_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
        options.datacenters = ['test', 'another']
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

        service_discovery = StubServiceDiscovery(options)
        service_discovery._update_upstreams_service('app', value_one_dc)
        service_discovery._update_upstreams_service('app', value_one_dc)

        assert len(service_discovery._upstreams_servers) == 1
        assert len(service_discovery.get_upstream('app').servers) == 1

    def test_multiple_update_upstreams_servers_different_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
        options.datacenters = ['test', 'another']
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

        service_discovery = StubServiceDiscovery(options)
        service_discovery._update_upstreams_service('app', value_one_dc)
        service_discovery._update_upstreams_service('app', value_another_dc)
        service_discovery._update_upstreams_service('app', value_another_dc)
        service_discovery._update_upstreams_service('app', value_one_dc)

        assert len(service_discovery._upstreams_servers) == 2
        assert len(service_discovery.get_upstream('app').servers) == 2

    def test_remove_upstreams_servers_different_dc(self) -> None:
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
        options.datacenters = ['test', 'another']
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

        service_discovery = StubServiceDiscovery(options)
        service_discovery._update_upstreams_service('app', value_test_dc)
        service_discovery._update_upstreams_service('app', value_another_dc)

        assert len(service_discovery._upstreams_servers['app-test']) == 1
        assert len(service_discovery._upstreams_servers['app-another']) == 2
        assert len(service_discovery.get_upstream('app').servers) == 3

        service_discovery._update_upstreams_service('app', value_another_remove_service_dc)

        assert len(service_discovery._upstreams_servers['app-another']) == 1
        assert service_discovery._upstreams_servers['app-another'][0].address == '2.2.2.2:9999'
        assert len(service_discovery.get_upstream('app').servers) == 3
        assert len([server for server in service_discovery.get_upstream('app').servers if server is not None]) == 2
