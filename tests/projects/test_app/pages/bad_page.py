# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback_error(element, response):
            if element is None:
                self.doc.put('42')
            else:
                self.doc.put('it can''t be')

        self_uri = self.request.host + self.request.path
        self.post_url(self_uri + '?mode=xml', callback=callback_error)
        self.post_url(self_uri + '?mode=json', callback=callback_error)

    def post_page(self):
        if self.get_argument('mode') == "xml":
            self.text = '''<doc frontik="tr"ue">this is broken xml</doc>'''
            self.set_header("Content-Type", "xml")
        elif self.get_argument('mode') == "json":
            self.text = '''{"hel"lo" : "this is broken json"}'''
            self.set_header("Content-Type", "json")
