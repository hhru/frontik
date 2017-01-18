# coding=utf-8

from frontik.handler import HTTPError, PageHandler


class Page(PageHandler):
    def prepare(self):
        self.register_before_finish_hook(self.before_finish_hook)
        if self.get_argument('exception_in_hook', 'false') == 'true':
            self.register_before_finish_hook(self.failing_before_finish_hook)

        super(Page, self).prepare()

    def get_page(self):
        self.text = 'content'

        if self.get_argument('exception_in_handler', 'false') == 'true':
            raise ValueError('unexpected error')

    def before_finish_hook(self):
        self.add_header('X-Custom-Header', 'value')

    def failing_before_finish_hook(self):
        raise HTTPError(400)
