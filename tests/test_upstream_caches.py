import unittest

import tornado

from frontik.service_discovery import UpstreamCaches
from .instances import frontik_test_app


class UpstreamCachesTestCase(unittest.TestCase):

    def setUp(self):
        frontik_test_app.start()

    def tearDown(self):
        frontik_test_app.stop()

    def test_update_upstreams_servers_different_dc(self):
        tornado.options.options.upstreams = ['app']
        tornado.options.options.datacenters = ['Test', 'AnoTher']
        value_one_dc = [
            {
                'Node': {
                    'ID': '1',
                    'Node': '',
                    'Address': '1.1.1.1',
                    'Datacenter': 'test',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        value_another_dc = [
            {
                'Node': {
                    'ID': '2',
                    'Node': '',
                    'Address': '2.2.2.2',
                    'Datacenter': 'another',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        upstream_cache = UpstreamCaches()
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers), 2)
        self.assertEqual(len(upstream_cache.upstreams['app'].servers), 2)

    def test_update_upstreams_servers_same_dc(self):
        tornado.options.options.upstreams = ['app']
        tornado.options.options.datacenters = ['test', 'another']
        value_one_dc = [
            {
                'Node': {
                    'ID': '1',
                    'Node': '',
                    'Address': '1.1.1.1',
                    'Datacenter': 'test',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        upstream_cache = UpstreamCaches()
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_one_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers), 1)
        self.assertEqual(len(upstream_cache.upstreams['app'].servers), 1)

    def test_multiple_update_upstreams_servers_different_dc(self):
        tornado.options.options.upstreams = ['app']
        tornado.options.options.datacenters = ['test', 'another']
        value_one_dc = [
            {
                'Node': {
                    'ID': '1',
                    'Node': '',
                    'Address': '1.1.1.1',
                    'Datacenter': 'test',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        value_another_dc = [
            {
                'Node': {
                    'ID': '2',
                    'Node': '',
                    'Address': '2.2.2.2',
                    'Datacenter': 'another',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        upstream_cache = UpstreamCaches()
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)
        upstream_cache._update_upstreams_service('app', value_one_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers), 2)
        self.assertEqual(len(upstream_cache.upstreams['app'].servers), 2)

    def test_remove_upstreams_servers_different_dc(self):
        tornado.options.options.upstreams = ['app']
        tornado.options.options.datacenters = ['test', 'another']
        value_test_dc = [
            {
                'Node': {
                    'ID': '1',
                    'Node': '',
                    'Address': '1.1.1.1',
                    'Datacenter': 'test',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        value_another_dc = [
            {
                'Node': {
                    'ID': '2',
                    'Node': '',
                    'Address': '2.2.2.2',
                    'Datacenter': 'another',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            },
            {
                'Node': {
                    'ID': '2',
                    'Node': '',
                    'Address': '2.2.2.2',
                    'Datacenter': 'another',
                },
                'Service': {
                    'ID': '3',
                    'Service': 'app',
                    'Address': '',
                    'Port': 999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        value_another_remove_service_dc = [
            {
                'Node': {
                    'ID': '2',
                    'Node': '',
                    'Address': '2.2.2.2',
                    'Datacenter': 'another',
                },
                'Service': {
                    'ID': '2',
                    'Service': 'app',
                    'Address': '',
                    'Port': 9999,
                    'Weights': {
                        'Passing': 100,
                        'Warning': 0
                    }
                }
            }
        ]

        upstream_cache = UpstreamCaches()
        upstream_cache._update_upstreams_service('app', value_test_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers['app-test']), 1)
        self.assertEqual(len(upstream_cache._upstreams_servers['app-another']), 2)
        self.assertEqual(len(upstream_cache.upstreams['app'].servers), 3)

        upstream_cache._update_upstreams_service('app', value_another_remove_service_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers['app-another']), 1)
        self.assertEqual(upstream_cache._upstreams_servers['app-another'][0].address, '2.2.2.2:9999')
        self.assertEqual(len(upstream_cache.upstreams['app'].servers), 2)
