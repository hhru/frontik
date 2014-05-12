# coding=utf-8

import unittest

from tornado.httpclient import HTTPRequest

from frontik.testing.service_mock import parse_query, route, route_less_or_equal_than, EmptyEnvironment
from frontik.testing.pages import Page


class TestServiceMock(unittest.TestCase):
    def test_parse_query_ok(self, ):
        self.assertEquals(parse_query('a=&z=q&vacancyId=1432459'), {'a': ('',), 'z': ('q',), 'vacancyId': ('1432459',)})

    def test_equal_route(self, ):
        self.assertTrue(route_less_or_equal_than(route("/abc/?q=1"), route("/abc/?q=1")),
                        "equal routes do not match each other")

    def test_swapped(self, ):
        self.assertTrue(route_less_or_equal_than(route("/abc/?a=2&q=1"), route("/abc/?q=1&a=2")),
                        "swapped query parameters do not match each other")

    def test_different_paths(self, ):
        self.assertFalse(route_less_or_equal_than(route("/abc?q=1"), route("/abc/?q=1")),
                         "different paths should not match")

    def test_right_query_is_less(self, ):
        self.assertFalse(route_less_or_equal_than(route("/abc/?a=2&q=1"), route("/abc/?q=1")),
                         "insufficient query parameters should not match")

    def test_routing_by_url(self, ):
        test_handler = '<xml></xml>'
        routes = {
            'test.ru': {
                '/handler': test_handler
            }
        }
        expecting_handler = EmptyEnvironment().expect(**routes)
        self.assertRaises(NotImplementedError, expecting_handler.route_request, HTTPRequest('http://test.ru/404'))
        self.assertEquals(expecting_handler.route_request(HTTPRequest('http://test.ru/handler')).body, test_handler)

    def test_get_doc_shows_what_expected(self, ):
        """ intergation test that shows test usage example """
        import lxml.etree
        from frontik.handler import HTTPError
        from frontik.async import AsyncGroup

        def function_under_test(handler):
            def finished():
                res = lxml.etree.Element("result")
                res.text = str(handler.result)
                handler.doc.put(res)
                handler.set_header('X-Foo', 'Bar')
                handler.set_status(400)

            handler.result = 0
            ag = AsyncGroup(finished)

            def accumulate(xml, response):
                if response.code >= 400:
                    raise HTTPError(503, "remote server returned error with code =" + str(response.code))
                if xml is None:
                    raise HTTPError(503)
                handler.result += int(xml.findtext("a"))

            handler.get_url(handler.config.serviceHost + 'vacancy/1234', callback=ag.add(accumulate))
            handler.get_url(handler.config.serviceHost + 'employer/1234', callback=ag.add(accumulate))

        class EtalonTest(unittest.TestCase):
            def runTest(self):
                result = EmptyEnvironment().expect(
                    serviceHost={
                        '/vacancy/1234': (200, '<b><a>1</a></b>'),
                        '/employer/1234': '<b><a>2</a></b>'
                    }
                ).call_function(function_under_test)

                self.assertEqual(result.get_doc().root_node.findtext('result'), '3')

                self.assertEqual(result.get_status(), 400)
                self.assertEqual(result.get_headers().get('X-Foo'), 'Bar')
                self.assertEqual(
                    result.get_response_text(),
                    '<?xml version=\'1.0\' encoding=\'utf-8\'?>\n<doc frontik="true"><result>3</result></doc>'
                )

                doc = EmptyEnvironment().call_get(Page).get_doc().root_node
                self.assertEquals(doc.findtext('hello'), 'Hello testing!')

        # test that test itself works (does not throw exception)
        unittest.TextTestRunner().run(EtalonTest())

if __name__ == '__main__':
    unittest.main()
