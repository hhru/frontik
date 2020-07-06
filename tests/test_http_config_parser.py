import unittest

from http_client import Upstream


class TestHttpConfigParser(unittest.TestCase):
    def test_single_server(self):
        config, servers = Upstream.parse_config(
            'max_tries=1 fail_timeout_sec=1 request_timeout_sec=0.2  max_fails=30 |server=172.17.0.1:2800  weight=100|')

        self.assertEqual('1', config['max_tries'])
        self.assertEqual('30', config['max_fails'])
        self.assertEqual('1', config['fail_timeout_sec'])
        self.assertEqual('0.2', config['request_timeout_sec'])
        self.assertEqual(1, len(servers))

        server = servers[0]
        self.assertEqual('172.17.0.1:2800', server.address)
        self.assertEqual(100, server.weight)

    def test_single_server_without_last_separator(self):
        config, servers = Upstream.parse_config('|server=bla-bla   fail_timeout_sec=1 max_fails=30 weight=1 ')

        self.assertEqual(0, len(config))
        self.assertEqual(1, len(servers))

        server = servers[0]
        self.assertEqual('bla-bla', server.address)
        self.assertEqual(1, server.weight)

    def test_multiple_servers(self):
        config, servers = Upstream.parse_config('|server=bla-bla weight=1 | server=someserver weight=2')

        self.assertEqual(0, len(config))
        self.assertEqual(2, len(servers))

        server = servers[0]
        self.assertEqual('bla-bla', server.address)
        self.assertEqual(1, server.weight)

        server = servers[1]
        self.assertEqual('someserver', server.address)
        self.assertEqual(2, server.weight)

    def test_defaults(self):
        config, servers = Upstream.parse_config('|server=bla-bla')

        self.assertEqual(0, len(config))
        self.assertEqual(1, len(servers))

        server = servers[0]
        self.assertEqual('bla-bla', server.address)
        self.assertEqual(1, server.weight)

    def test_ignoring_parameters(self):
        config, servers = Upstream.parse_config('abb=2|server=bla-bla some_parameter=434')

        self.assertEqual('2', config['abb'])
        self.assertEqual(1, len(servers))

        server = servers[0]
        self.assertEqual('bla-bla', server.address)

    def test_rack_and_datacenter_parameters(self):
        config, servers = Upstream.parse_config('|server=s1 rack=r1 dc=dc1|server=s2 rack=r2 dc=dc2')

        self.assertEqual(2, len(servers))

        server = servers[0]
        self.assertEqual('s1', server.address)
        self.assertEqual('r1', server.rack)
        self.assertEqual('dc1', server.datacenter)

        server = servers[1]
        self.assertEqual('s2', server.address)
        self.assertEqual('r2', server.rack)
        self.assertEqual('dc2', server.datacenter)
