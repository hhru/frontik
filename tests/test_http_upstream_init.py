# coding=utf-8

import unittest

# noinspection PyUnresolvedReferences
import frontik.options

from frontik.http_client import HttpClientFactory


class TestHttpUpstreamInit(unittest.TestCase):
    def test_init_from_config(self):
        http_client_factory = HttpClientFactory({
            'nn': {'config': {'max_tries': 10, 'max_fails': 100,
                              'request_timeout_sec': 0.1, 'connect_timeout_sec': 1.3, 'max_timeout_tries': 4},
                   'servers': [{'server': '172.17.0.1:2800'}]}
        })

        upstream = http_client_factory.upstreams.get('nn')

        self.assertEquals(10, upstream.max_tries)
        self.assertEquals(100, upstream.max_fails)
        self.assertEquals(10, upstream.fail_timeout)
        self.assertEquals(1.3, upstream.connect_timeout)
        self.assertEquals(0.1, upstream.request_timeout)
        self.assertEquals(4, upstream.max_timeout_tries)

        self.assertEquals(1, len(upstream.servers))
        self.assertEquals('172.17.0.1:2800', upstream.servers[0].address)

    def test_from_config_string(self):
        http_client_factory = HttpClientFactory({})

        http_client_factory.update_upstream(
            'nn',
            'max_tries=10 fail_timeout_sec=1 max_fails=30 request_timeout_sec=0.2 '
            'connect_timeout_sec=1 max_timeout_tries=2 |'
            'server=172.17.0.1:2800')
        upstream = http_client_factory.upstreams.get('nn')

        self.assertEquals(10, upstream.max_tries)
        self.assertEquals(30, upstream.max_fails)
        self.assertEquals(1, upstream.fail_timeout)
        self.assertEquals(1, upstream.connect_timeout)
        self.assertEquals(0.2, upstream.request_timeout)
        self.assertEquals(2, upstream.max_timeout_tries)

        self.assertEquals(1, len(upstream.servers))
        self.assertEquals('172.17.0.1:2800', upstream.servers[0].address)

    def test_retry_policy(self):
        http_client_factory = HttpClientFactory({})

        http_client_factory.update_upstream('nn', 'retry_policy=http_503,non_idempotent_503|server=172.17.0.1:2800')
        upstream = http_client_factory.upstreams.get('nn')
        self.assertEquals({503: True}, upstream.retry_policy.statuses)

    def test_remove(self):
        http_client_factory = HttpClientFactory({})

        http_client_factory.update_upstream('nn', 'max_tries=10 | server=172.17.0.1:2800')
        self.assertEquals(1, len(http_client_factory.upstreams))

        http_client_factory.update_upstream('nn', None)
        self.assertEquals(0, len(http_client_factory.upstreams))

    def test_empty_server_list_init(self):
        http_client_factory = HttpClientFactory({})

        http_client_factory.update_upstream('nn', '|')
        self.assertEquals(0, len(http_client_factory.upstreams))

    def test_empty_server_list_update(self):
        http_client_factory = HttpClientFactory({})

        http_client_factory.update_upstream('nn', 'max_tries=10 | server=172.17.0.1:2800')
        self.assertEquals(1, len(http_client_factory.upstreams))

        http_client_factory.update_upstream('nn', '|')
        self.assertEquals(0, len(http_client_factory.upstreams))
