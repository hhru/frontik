# coding=utf-8

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        self.text = 'old bad text'

        def callback_post(element, response):
            assert False

        url = 'http://localhost:{0}/test_app/post_simple/'.format(self.get_argument('port'))
        self.post_url(url, callback=callback_post)
        self.post_url(url, callback=callback_post)
        self.post_url(url, callback=callback_post)
        self.post_url(url, callback=callback_post)

        raise frontik.handler.HTTPError(403, text='This is just a plain text')
        self.text = 'absolutely not forty two, no way'
