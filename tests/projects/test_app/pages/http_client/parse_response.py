# coding=utf-8

from tornado.escape import to_unicode

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self_uri = self.request.host + self.request.path
        self.json.put(self.post_url(self_uri, parse_on_error=True))
        self.json.put(self.put_url(self_uri, parse_on_error=False))

        self.delete_url(self_uri, parse_response=False, callback=self.delete_callback)

    def delete_callback(self, data, response):
        self.json.put({'delete': to_unicode(data)})

    def post_page(self):
        raise frontik.handler.HTTPError(400, json={'post': True})

    def put_page(self):
        raise frontik.handler.HTTPError(400, json={'put': True})

    def delete_page(self):
        self.text = 'deleted'
