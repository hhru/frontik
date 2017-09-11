# coding=utf-8

import unittest

# noinspection PyUnresolvedReferences
import frontik.options

from frontik.http_client import HttpClientFactory


class TestHttpUpstreamInit(unittest.TestCase):
    def test_init_from_config(self):
        http_client_factory = HttpClientFactory(None, {
            'nn': {'config': {'tries': 10, 'max_fails': 100}, 'servers': [{'server': '172.17.0.1:2800'}]}
        })

        upstream = http_client_factory.upstreams.get('nn')

        self.assertEquals(10, upstream.tries)
        self.assertEquals(100, upstream.max_fails)
        self.assertEquals(10, upstream.fail_timeout)

        self.assertEquals(1, len(upstream.servers))
        self.assertEquals('172.17.0.1:2800', upstream.servers[0].address)

    def test_from_config_string(self):
        http_client_factory = HttpClientFactory(None, {})

        http_client_factory.update_upstream('nn', 'tries=10 fail_timeout=1 max_fails=30 | server=172.17.0.1:2800')
        upstream = http_client_factory.upstreams.get('nn')

        self.assertEquals(10, upstream.tries)
        self.assertEquals(30, upstream.max_fails)
        self.assertEquals(1, upstream.fail_timeout)

        self.assertEquals(1, len(upstream.servers))
        self.assertEquals('172.17.0.1:2800', upstream.servers[0].address)

    def test_remove(self):
        http_client_factory = HttpClientFactory(None, {})

        http_client_factory.update_upstream('nn', 'tries=10 | server=172.17.0.1:2800')
        self.assertEquals(1, len(http_client_factory.upstreams))

        http_client_factory.update_upstream('nn', None)
        self.assertEquals(0, len(http_client_factory.upstreams))

    def test_empty_server_list_init(self):
        http_client_factory = HttpClientFactory(None, {})

        http_client_factory.update_upstream('nn', '|')
        self.assertEquals(0, len(http_client_factory.upstreams))

    def test_empty_server_list_update(self):
        http_client_factory = HttpClientFactory(None, {})

        http_client_factory.update_upstream('nn', 'tries=10 | server=172.17.0.1:2800')
        self.assertEquals(1, len(http_client_factory.upstreams))

        http_client_factory.update_upstream('nn', '|')
        self.assertEquals(0, len(http_client_factory.upstreams))
