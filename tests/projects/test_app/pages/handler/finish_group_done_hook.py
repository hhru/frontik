# coding=utf-8

from frontik.handler import HTTPError, PageHandler


class Page(PageHandler):
    def prepare(self):
        self.register_finish_group_done_hook(self.finish_group_done_hook)
        if self.get_argument('exception_in_hook', 'false') == 'true':
            self.register_finish_group_done_hook(self.failing_finish_group_done_hook)

        super(Page, self).prepare()

    def get_page(self):
        self.text = 'content'

        if self.get_argument('exception_in_handler', 'false') == 'true':
            raise ValueError('unexpected error')

    def finish_group_done_hook(self):
        self.add_header('X-Custom-Header', 'value')

    def failing_finish_group_done_hook(self):
        raise HTTPError(400)
