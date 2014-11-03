import frontik.handler
import httplib


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def _cb(data, response):
            if data == '' and response.code == httplib.OK:
                self.text = 'OK'

        self.head_url(self.request.host+'/head', callback=_cb)
