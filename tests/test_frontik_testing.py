# coding=utf-8

import sys
import traceback
import unittest

import lxml.etree
from tornado.httpclient import HTTPRequest

from frontik.async import AsyncGroup
from frontik.handler import HTTPError, PageHandler
from frontik.testing.service_mock import route, route_less_or_equal_than, EmptyEnvironment
from frontik.testing.pages import Page
from . import py3_skip


class TestPage(PageHandler):
    def get_page(self):
        def finished():
            res = lxml.etree.Element('result')
            res.text = str(self.result)
            self.doc.put(res)
            self.set_header('X-Foo', 'Bar')
            self.set_status(400)

        self.result = 0
        ag = AsyncGroup(finished)

        def accumulate(xml, response):
            if response.code >= 400:
                raise HTTPError(503, 'remote server returned error with code {}'.format(response.code))
            if xml is None:
                raise HTTPError(503)
            self.result += int(xml.findtext('a'))

        self.get_url(self.config.serviceHost + 'vacancy/1234', callback=ag.add(accumulate))
        self.get_url(self.config.serviceHost + 'employer/1234', callback=ag.add(accumulate))


class TestServiceMock(unittest.TestCase):
    def test_equal_route(self):
        self.assertTrue(
            route_less_or_equal_than(route('/abc/?q=1'), route('/abc/?q=1')), 'equal routes do not match each other'
        )

    def test_swapped(self):
        self.assertTrue(
            route_less_or_equal_than(route('/abc/?a=2&q=1'), route('/abc/?q=1&a=2')),
            'swapped query parameters do not match each other'
        )

    def test_different_paths(self):
        self.assertTrue(
            route_less_or_equal_than(route('/abc?q=1'), route('/abc/?q=1')),
            'paths with and w/o trailing slash at the end should match'
        )

    def test_right_query_is_less(self):
        self.assertFalse(
            route_less_or_equal_than(route('/abc/?a=2&q=1'), route('/abc/?q=1')),
            'insufficient query parameters should not match'
        )

    def test_config(self):
        class CheckConfigHandler(PageHandler):
            def get_page(self):
                assert self.config.config_param

        EmptyEnvironment().configure(config_param=True).call_get(CheckConfigHandler)

    def test_routing_by_url(self):
        test_handler = '<xml></xml>'
        routes = {
            'test.ru': {
                '/handler': test_handler
            }
        }
        expecting_handler = EmptyEnvironment().expect(**routes)
        self.assertRaises(NotImplementedError, expecting_handler.route_request, HTTPRequest('http://test.ru/404'))
        self.assertEquals(expecting_handler.route_request(HTTPRequest('http://test.ru/handler')).body, test_handler)

    @py3_skip
    def test_call_function(self):
        result = EmptyEnvironment().expect(
            serviceHost={
                '/vacancy/1234': (200, '<b><a>1</a></b>'),
                '/employer/1234': '<b><a>2</a></b>'
            }
        ).call_get(TestPage)

        self.assertEqual(result.get_xml_response().findtext('result'), '3')
        self.assertEqual(result.get_status(), 400)
        self.assertEqual(result.get_headers().get('X-Foo'), 'Bar')
        self.assertEqual(
            result.get_text_response(),
            '<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<doc><result>3</result></doc>'
        )

    @py3_skip
    def test_call_get(self):
        result = EmptyEnvironment().add_arguments({'param': 'world'}).call_get(Page)
        self.assertEqual(result.get_json_response()['Hello'], 'world')

    @py3_skip
    def test_exception(self):
        class ExceptionHandler(PageHandler):
            def get_page(self):
                def _inner():
                    raise HTTPError(500, 'fail')
                _inner()

        try:
            EmptyEnvironment().call_get(ExceptionHandler, raise_exceptions=True)
        except HTTPError as e:
            self.assertEqual(e.status_code, 500)
            self.assertEqual(e.log_message, 'fail')

            tb = ''.join(traceback.format_tb(sys.exc_traceback))
            self.assertIn('_inner()', tb)
        else:
            self.fail('HTTPError must be raised')
