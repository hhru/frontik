from tornado.httpclient import HTTPRequest

import unittest

from frontik.testing.service_mock import parse_query, route, route_less_or_equal_than, expecting

class TestServiceMock(unittest.TestCase):
    def test_parse_query_ok(self, ):
        self.assertEquals(parse_query('a=&z=q&vacancyId=1432459'), {'a' : ('',), 'z' : ('q',), 'vacancyId' : ('1432459',)})
    def test_equal_route(self, ):
        self.assertTrue(route_less_or_equal_than(route("/abc/?q=1"), route("/abc/?q=1")), "equal routes do not match each other")
    def test_swapped(self, ):
        self.assertTrue(route_less_or_equal_than(route("/abc/?a=2&q=1"), route("/abc/?q=1&a=2")), "swapped query parameters do not match each other")
    def test_different_paths(self, ):
        self.assertFalse(route_less_or_equal_than(route("/abc?q=1"), route("/abc/?q=1")), "different paths should not match")
    def test_right_query_is_less(self, ):
        self.assertFalse(route_less_or_equal_than(route("/abc/?a=2&q=1"), route("/abc/?q=1")), "insufficient query parameters should not match")

    def test_routing_by_url(self, ):
        gogogo_handler = '<xml></xml>'
        routes = {'asdasd.ru' : {
                '/gogogo' : gogogo_handler
            } }
        expecting_handler = expecting( **routes )
        self.assertRaises(NotImplementedError, expecting_handler.route_request, HTTPRequest('http://asdasd.ru/nonono'))
        assert expecting_handler.route_request(HTTPRequest('http://asdasd.ru/gogogo')).body == gogogo_handler

    def test_get_doc_shows_what_expected(self, ):
        '''intergation test that shows main test path'''
        import lxml.etree
        from frontik.handler import HTTPError, AsyncGroup

        def function_under_test(handler, ):
            def finished():
                res = lxml.etree.Element("result")
                res.text = str(handler.result)
                handler.doc.put(res)
                handler.finish()

            handler.result = 0
            ag = AsyncGroup(finished)
            def accumulate(xml, response):
                if response.code >= 400:
                    raise HTTPError(503, "remote server returned error with code =" + str(response.code))
                if xml is None:
                    raise HTTPError(503)
                handler.result += int(xml.findtext("a"))

            handler.get_url(handler.config.serviceHost +  'vacancy/1234', callback = ag.add(accumulate))
            handler.get_url(handler.config.serviceHost + 'employer/1234', callback = ag.add(accumulate))

        class EtalonTest(unittest.TestCase):
            def runTest(self,):
                doc = expecting(serviceHost = {
                        '/vacancy/1234' : (200, '<b><a>1</a></b>'),
                        '/employer/1234' : '<b><a>2</a></b>'
                }).call(function_under_test).get_doc().root_node

                self.assertEqual(doc.findtext('result'), '3')

        #test that test works (does not throw exception)
        ts = unittest.TestSuite()
        ts.addTest(EtalonTest())
        tr = unittest.TextTestRunner()
        tr.run(ts)

if __name__ == '__main__':
    unittest.main()


