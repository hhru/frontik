# coding=utf-8

import os
import unittest
from functools import partial

from lxml import etree
from tornado.escape import to_unicode

from frontik.app import FrontikApplication
from frontik.async import AsyncGroup
from frontik.handler import HTTPError, PageHandler
from frontik.testing import get_response_stub, FrontikTestCase, patch_http_client
from frontik.testing.service_mock import route, routes_match
from .projects.test_app.pages.arguments import Page


class RoutesMatchTest(unittest.TestCase):
    def test_equal_route(self):
        self.assertTrue(
            routes_match(route('/abc/?q=1'), route('/abc/?q=1')),
            'Equal routes must match'
        )

    def test_swapped(self):
        self.assertTrue(
            routes_match(route('/abc/?a=2&q=1'), route('/abc/?q=1&a=2')),
            'Routes with different parameters order must match'
        )

    def test_different_paths(self):
        self.assertTrue(
            routes_match(route('/abc?q=1'), route('/abc/?q=1')),
            'Routes with and without trailing slash must match'
        )

    def test_right_query_is_less(self):
        self.assertFalse(
            routes_match(route('/abc/?a=2&q=1'), route('/abc/?q=1')),
            'insufficient query parameters should not match'
        )


class TestPage(PageHandler):
    def get_page(self):
        def finished():
            res = etree.Element('result')
            res.text = str(self.result)
            self.doc.put(res)
            self.set_header('X-Foo', self.request.headers.get('X-Foo'))
            self.set_status(400)

        self.result = 0
        ag = AsyncGroup(finished)

        def accumulate(xml, response):
            if response.code >= 400 or xml is None:
                raise HTTPError(503)

            self.result += int(xml.findtext('id'))

        self.get_url(self.config.serviceHost + '/vacancy/1', callback=ag.add(accumulate))
        self.get_url(self.config.serviceHost + '/employer/2', callback=ag.add(accumulate))


class CheckConfigHandler(PageHandler):
    def get_page(self):
        assert self.config.config_param


class ExceptionHandler(PageHandler):
    def get_page(self):
        raise HTTPError(500)


class TestApplication(FrontikApplication):
    def application_urls(self):
        return [
            ('/config', CheckConfigHandler),
            ('/sum_ids', TestPage),
            ('/proxy_arg', Page),
            ('/exception', ExceptionHandler),
        ]


class TestFrontikTesting(FrontikTestCase):
    def setUp(self):
        super(TestFrontikTesting, self).setUp()
        self.configure_app(serviceHost='http://service.host')
        self.add_common_headers({'X-Foo': 'Bar'})

    def get_app(self):
        app = TestApplication(app='test_app')
        patch_http_client(app.http_client, os.path.dirname(__file__))
        return app

    def test_config(self):
        self.configure_app(config_param=True)
        response = self.fetch('/config')

        self.assertEqual(200, response.code)

    def test_stubs_no_stub(self):
        response = self.fetch('/sum_ids')
        self.assertEqual(response.code, 500)

    def test_stubs_response_code(self):
        self.set_stub(('service.host', '/vacancy/1'), response_code=404)
        self.set_stub(('service.host', '/employer/2'), response_code=404)

        response = self.fetch('/sum_ids')

        self.assertEqual(response.code, 503)

    def test_stubs_raw_response(self):
        self.set_stub(
            ('service.host', '/vacancy/1'),
            raw_response='<root><id>3</id></root>', headers={'Content-Type': 'application/xml'}
        )

        self.set_stub(
            ('service.host', '/employer/{employer_id}'),
            raw_response='<root><id>4</id></root>', headers={'Content-Type': 'application/xml'},
            employer_id='2'
        )

        response = self.fetch('/sum_ids')

        self.assertEqual(response.code, 400)
        self.assertEqual(response.headers.get('X-Foo'), 'Bar')
        self.assertEqual(
            response.body,
            b'<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<doc><result>7</result></doc>'
        )

    def test_stubs_response_file(self):
        self.set_stub(('service.host', '/vacancy/{id}'), response_file='stub.xml', id='1')
        self.set_stub(('service.host', '/employer/{id}'), response_file='stub.xml', id='2')

        doc = self.fetch_xml('/sum_ids')

        self.assertEqual(doc.findtext('result'), '3')

    def test_stubs_response_file_missing_template(self):
        self.set_stub(('service.host', '/vacancy/1'), response_file='stub_missing.xml', param='param')
        self.set_stub(('service.host', '/employer/2'), response_file='stub_missing.xml')

        doc = self.fetch_xml('/sum_ids')

        self.assertEqual(doc.findtext('result'), '0')

    def test_stubs_response_function(self):
        self.set_stub(
            ('service.host', '/vacancy/1'),
            response_function=partial(
                get_response_stub, buffer='<root><id>0</id></root>', headers={'Content-Type': 'application/xml'}
            )
        )

        self.set_stub(
            ('service.host', '/employer/2'),
            response_function=partial(
                get_response_stub, buffer='<root><id>0</id></root>', headers={'Content-Type': 'application/xml'}
            )
        )

        doc = self.fetch_xml('/sum_ids')

        self.assertEqual(doc.findtext('result'), '0')

    def test_call_get(self):
        json = self.fetch_json('/proxy_arg', {'param': 'тест'})
        self.assertEqual(to_unicode(json[u'тест']), u'тест')

    def test_exception(self):
        response = self.fetch('/exception')
        self.assertEqual(response.code, 500)
