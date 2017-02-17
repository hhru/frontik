# coding=utf-8

import os
import unittest
from functools import partial

from lxml import etree
from tornado.escape import to_unicode

from frontik.app import FrontikApplication
from frontik.handler import HTTPError, PageHandler
from frontik.testing import get_response_stub, FrontikTestCase, patch_http_client, route, routes_match
from .projects.test_app.pages import arguments
from .projects.test_app.pages.handler import delete


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
            'Less specific route must not match more specific'
        )

    def test_routes_with_different_methods(self):
        self.assertFalse(
            routes_match(route('/abc'), route('/abc', method='POST')),
            'Routes with different methods must not match'
        )


class TestHandler(PageHandler):
    def get_page(self):
        self.result = 0

        def finished(_):
            res = etree.Element('result')
            res.text = str(self.result)
            self.doc.put(res)

            self.set_header('X-Foo', self.request.headers.get('X-Foo'))
            self.set_status(400)

        def accumulate(xml, response):
            if response.error or xml is None:
                raise HTTPError(503)

            try:
                self.result += int(xml.findtext('val'))
            except ValueError:
                pass

        self.group({
            'val1': self.get_url(self.config.serviceHost + '/val1/1', callback=accumulate),
            'val2': self.get_url(self.config.serviceHost + '/val2/2', callback=accumulate)
        }, callback=finished)


class CheckConfigHandler(PageHandler):
    def get_page(self):
        self.text = self.config.config_param


class ExceptionHandler(PageHandler):
    def get_page(self):
        raise HTTPError(500)


class TestFrontikTesting(FrontikTestCase):
    def setUp(self):
        super(TestFrontikTesting, self).setUp()
        self.configure_app(serviceHost='http://service.host')
        self.add_common_headers({'X-Foo': 'Bar'})

    def get_app(self):
        class TestApplication(FrontikApplication):
            def application_urls(self):
                return [
                    ('/config', CheckConfigHandler),
                    ('/sum_values', TestHandler),
                    ('/exception', ExceptionHandler),
                    ('/arguments', arguments.Page),
                    ('/delete', delete.Page),
                ]

        app = TestApplication(app='test_app')
        patch_http_client(app.http_client, os.path.dirname(__file__))

        return app

    def test_config(self):
        self.configure_app(config_param='param_value')
        response = self.fetch('/config')

        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'param_value')

    def test_stubs_no_stub(self):
        response = self.fetch('/sum_values')
        self.assertEqual(response.code, 500)

    def test_stubs_response_code(self):
        self.set_stub(('service.host', '/val1/1'), response_code=404)
        self.set_stub(('service.host', '/val2/2'), response_code=404)

        response = self.fetch('/sum_values')

        self.assertEqual(response.code, 503)

    def test_stubs_raw_response(self):
        self.set_stub(
            ('service.host', '/val1/1'),
            raw_response='<root><val>3</val></root>', headers={'Content-Type': 'application/xml'}
        )

        self.set_stub(
            ('service.host', '/val2/{id}'),
            raw_response='<root><val>4</val></root>', headers={'Content-Type': 'application/xml'},
            id='2'
        )

        response = self.fetch('/sum_values')

        self.assertEqual(response.code, 400)
        self.assertEqual(response.headers.get('X-Foo'), 'Bar')
        self.assertEqual(
            response.body,
            b'<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<doc><result>7</result></doc>'
        )

    def test_stubs_response_file(self):
        self.set_stub(('service.host', '/val1/{id}'), response_file='stub.xml', id='1')
        self.set_stub(('service.host', '/val2/{id}'), response_file='stub.xml', id='2')

        doc = self.fetch_xml('/sum_values')

        self.assertEqual(doc.findtext('result'), '3')

    def test_stubs_response_file_missing_template(self):
        self.set_stub(('service.host', '/val1/{id}'), response_file='stub.xml', id='1')
        self.set_stub(('service.host', '/val2/2'), response_file='stub.xml')

        doc = self.fetch_xml('/sum_values')

        self.assertEqual(doc.findtext('result'), '1')

    def test_stubs_response_function(self):
        self.set_stub(
            ('service.host', '/val1/1'),
            response_function=partial(
                get_response_stub, buffer='<root><val>0</val></root>', headers={'Content-Type': 'application/xml'}
            )
        )

        self.set_stub(
            ('service.host', '/val2/2'),
            response_function=partial(
                get_response_stub, buffer='<root><val>4</val></root>', headers={'Content-Type': 'application/xml'}
            )
        )

        doc = self.fetch_xml('/sum_values')

        self.assertEqual(doc.findtext('result'), '4')

    def test_json_stub(self):
        self.set_stub(
            ('localhost:{}'.format(self.get_http_port()), route('/delete', method='DELETE')),
            response_file='stub.json', param='param'
        )

        json = self.fetch_json('/delete')
        self.assertEqual(json, {'result': 'param'})

    def test_arguments(self):
        json = self.fetch_json('/arguments', {'param': 'тест'})
        self.assertEqual(to_unicode(json[u'тест']), u'тест')

    def test_exception(self):
        response = self.fetch('/exception')
        self.assertEqual(response.code, 500)
