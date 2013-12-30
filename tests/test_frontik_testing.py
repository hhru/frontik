# coding=utf-8

import sys
import traceback
import unittest

import lxml.etree
from tornado.httpclient import HTTPRequest

from frontik.async import AsyncGroup
from frontik.handler import HTTPError
from frontik.testing.service_mock import parse_query, route, route_less_or_equal_than, EmptyEnvironment
from frontik.testing.pages import Page


def _function_under_test(handler):
    def finished():
        res = lxml.etree.Element('result')
        res.text = str(handler.result)
        handler.doc.put(res)
        handler.set_header('X-Foo', 'Bar')
        handler.set_status(400)

    handler.result = 0
    ag = AsyncGroup(finished)

    def accumulate(xml, response):
        if response.code >= 400:
            raise HTTPError(503, 'remote server returned error with code {}'.format(response.code))
        if xml is None:
            raise HTTPError(503)
        handler.result += int(xml.findtext('a'))

    handler.get_url(handler.config.serviceHost + 'vacancy/1234', callback=ag.add(accumulate))
    handler.get_url(handler.config.serviceHost + 'employer/1234', callback=ag.add(accumulate))


class TestServiceMock(unittest.TestCase):
    def test_parse_query_ok(self):
        self.assertEquals(parse_query('a=&z=q&vacancyId=1432459'), {'a': ('',), 'z': ('q',), 'vacancyId': ('1432459',)})

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
        def check_config(handler):
            self.assertTrue(handler.config.config_param)

        EmptyEnvironment().configure(config_param=True).call_function(check_config)

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

    def test_call_function(self):
        result = EmptyEnvironment().expect(
            serviceHost={
                '/vacancy/1234': (200, '<b><a>1</a></b>'),
                '/employer/1234': '<b><a>2</a></b>'
            }
        ).call_function(_function_under_test)

        self.assertEqual(result.get_xml_response().findtext('result'), '3')
        self.assertEqual(result.get_status(), 400)
        self.assertEqual(result.get_headers().get('X-Foo'), 'Bar')
        self.assertEqual(
            result.get_text_response(),
            '<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<doc frontik="true"><result>3</result></doc>'
        )

    def test_call_get(self):
        result = EmptyEnvironment().add_arguments({'param': 'world'}).call_get(Page)
        self.assertEqual(result.get_json_response()['Hello'], 'world')

    def test_exception(self):
        def _test_function(handler):
            def _inner():
                raise HTTPError(500, 'fail')
            _inner()

        try:
            EmptyEnvironment().call_function(_test_function)
        except Exception as e:
            self.assertEqual(e.status_code, 500)
            self.assertEqual(e.log_message, 'fail')

            tb = ''.join(traceback.format_tb(sys.exc_traceback))
            self.assertIn('_inner()', tb)
