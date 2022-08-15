import asyncio
import os
import time
import unittest
from queue import Queue
from threading import Thread

from frontik.options import options
from frontik.service_discovery import UpstreamCaches, UpstreamUpdateListener
from http_client import Upstream, Server, options as http_client_options


class UpstreamCachesTestCase(unittest.TestCase):

    def test_update_upstreams_servers_different_dc(self):
        options.upstreams = ['app']
        http_client_options.datacenters = ['Test', 'AnoTher']
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

        upstream_cache = UpstreamCaches({}, {})
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers), 2)
        self.assertEqual(len(upstream_cache._upstreams['app'].servers), 2)

    def test_update_upstreams_servers_same_dc(self):
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
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

        upstream_cache = UpstreamCaches({}, {})
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_one_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers), 1)
        self.assertEqual(len(upstream_cache._upstreams['app'].servers), 1)

    def test_multiple_update_upstreams_servers_different_dc(self):
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
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

        upstream_cache = UpstreamCaches({}, {})
        upstream_cache._update_upstreams_service('app', value_one_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)
        upstream_cache._update_upstreams_service('app', value_one_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers), 2)
        self.assertEqual(len(upstream_cache._upstreams['app'].servers), 2)

    def test_remove_upstreams_servers_different_dc(self):
        options.upstreams = ['app']
        http_client_options.datacenters = ['test', 'another']
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

        upstream_cache = UpstreamCaches({}, {})
        upstream_cache._update_upstreams_service('app', value_test_dc)
        upstream_cache._update_upstreams_service('app', value_another_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers['app-test']), 1)
        self.assertEqual(len(upstream_cache._upstreams_servers['app-another']), 2)
        self.assertEqual(len(upstream_cache._upstreams['app'].servers), 3)

        upstream_cache._update_upstreams_service('app', value_another_remove_service_dc)

        self.assertEqual(len(upstream_cache._upstreams_servers['app-another']), 1)
        self.assertEqual(upstream_cache._upstreams_servers['app-another'][0].address, '2.2.2.2:9999')
        self.assertEqual(len(upstream_cache._upstreams['app'].servers), 3)
        self.assertEqual(len([server for server in upstream_cache._upstreams['app'].servers if server is not None]), 2)

    def test_pipe_buffer_overflow(self):
        options.upstreams = ['app']
        http_client_options.datacenters = ['Test']

        read_fd, write_fd = os.pipe2(os.O_NONBLOCK)
        upstreams = {
            'upstream': Upstream('upstream', {
                'max_timeout_tries': 10,
                'retry_policy': {
                    '403': {'idempotent': 'false'},
                    '500': {'idempotent': 'true'}
                }}, [Server('12.2.3.5'), Server('12.22.3.5')])
        }
        upstream_cache = UpstreamCaches({0: os.fdopen(write_fd, 'wb')}, upstreams)

        for i in range(200):
            upstream_cache.send_updates()

        self.assertTrue(upstream_cache._resend_dict, 'resend dict should not be empty')

        listener_upstreams = {}
        notification_queue = Queue()

        class ListenerCallback:
            def update_upstream(self, upstream):
                listener_upstreams[upstream.name] = upstream
                notification_queue.put(True)

        async def _listener():
            UpstreamUpdateListener(ListenerCallback(), read_fd)

        def _run_loop(io_loop):
            asyncio.set_event_loop(io_loop)
            io_loop.run_forever()

        loop = asyncio.new_event_loop()
        listener_thread = Thread(target=_run_loop, args=(loop,), daemon=True)
        listener_thread.start()

        asyncio.run_coroutine_threadsafe(_listener(), loop)

        notification_queue.get()
        while not notification_queue.empty():
            notification_queue.get()

        self.assertEqual(1, len(listener_upstreams), 'upstreams size on master and worker should be the same')

        upstreams['upstream2'] = Upstream('upstream2', {}, [Server('12.2.3.5'), Server('12.22.3.5')])

        upstream_cache.send_updates()
        upstream_cache.send_updates()

        notification_queue.get()
        while not notification_queue.empty():
            notification_queue.get()

        time.sleep(0.5)

        self.assertEqual(2, len(listener_upstreams), 'upstreams size on master and worker should be the same')
