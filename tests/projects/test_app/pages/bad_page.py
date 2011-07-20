import frontik.handler
import lxml.etree as etree
import re

class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback_error(element, response):
            if element is None:
                self.doc.put("42")
            else:
                self.doc.put("it's cant be")

        self.post_url("http://localhost:{0}/test_app/bad_page/?mode=xml".format(self.get_argument('port')), callback=callback_error)
        self.post_url("http://localhost:{0}/test_app/bad_page/?mode=json".format(self.get_argument('port')), callback=callback_error)


    def post_page(self):
        if self.get_argument('mode') == "xml":
            self.text = '''<doc frontik="tr"ue">this is broken xml</doc>'''
            self.set_header("Content-Type", "xml")
        elif self.get_argument('mode') == "json":
            self.text = '''{"hel"lo" : "this is broken json"}'''
            self.set_header("Content-Type", "json")

