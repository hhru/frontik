from lxml import etree

from frontik.app import FrontikApplication
from frontik.handler import PageHandler
from frontik.testing import FrontikTestCase
from tests.projects.test_app.pages.handler import delete


class AsyncHandler(PageHandler):
    def get_page(self):
        self.result = 0

        def finished(_):
            res = etree.Element('result')
            res.text = str(self.result)
            self.doc.put(res)
            self.set_status(400)

        def accumulate(xml, response):
            self.result += int(xml.findtext('val'))

        self.group({
            'val1': self.get_url(self.config.serviceHost, '/val1/1', callback=accumulate),
            'val2': self.get_url(self.config.serviceHost, '/val2/2', callback=accumulate)
        }, callback=finished)


class CheckConfigHandler(PageHandler):
    def get_page(self):
        self.text = self.config.config_param


class TestFrontikTesting(FrontikTestCase):
    def setUp(self):
        super().setUp()
        self.configure_app(serviceHost='http://service.host')

    def get_app(self):
        class TestApplication(FrontikApplication):
            def application_urls(self):
                return [
                    ('/config', CheckConfigHandler),
                    ('/sum_values', AsyncHandler),
                    ('/delete', delete.Page),
                ]

        app = TestApplication(app='test_app')
        self.patch_app_http_client(app)

        return app

    def test_config(self):
        self.configure_app(config_param='param_value')
        response = self.fetch('/config')

        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b'param_value')

    def test_xml_stub(self):
        self.set_stub('http://service.host/val1/$id', response_file='tests/stub.xml', id='1', val='2')
        self.set_stub('http://service.host/val2/2', response_file='tests/stub.xml', val='3')

        doc = self.fetch_xml('/sum_values')

        self.assertEqual(doc.findtext('result'), '5')

    def test_json_stub(self):
        self.set_stub(
            'http://127.0.0.1:{}/delete'.format(self.get_http_port()), request_method='DELETE',
            response_file='tests/stub.json', param='param'
        )

        json = self.fetch_json('/delete')
        self.assertEqual(json, {'result': 'param'})
