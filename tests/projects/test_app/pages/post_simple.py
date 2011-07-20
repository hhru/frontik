import frontik.handler

class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback_post(element, response):
            self.doc.put(element.text)

        self.post_url("http://localhost:{0}/test_app/post_simple/".format(self.get_argument('port')), callback=callback_post)


    def post_page(self):
        self.doc.put("42")
