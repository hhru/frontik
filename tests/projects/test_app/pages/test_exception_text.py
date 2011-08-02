import frontik.handler
import lxml.etree as etree

class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.text = "old bad text"

        def callback_post(element, response):
            assert False

        self.post_url("http://localhost:{0}/test_app/post_simple/".format(self.get_argument('port')), callback=callback_post)
        self.post_url("http://localhost:{0}/test_app/post_simple/".format(self.get_argument('port')), callback=callback_post)
        self.post_url("http://localhost:{0}/test_app/post_simple/".format(self.get_argument('port')), callback=callback_post)
        self.post_url("http://localhost:{0}/test_app/post_simple/".format(self.get_argument('port')), callback=callback_post)

        raise frontik.handler.HTTPError(status_code=202, text = "This is just a plain text")
        self.text = "absolutely not forty two, no way"
