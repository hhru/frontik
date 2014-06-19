# coding=utf-8

from frontik.handler import HTTPError, PageHandler


def first_preprocessor(handler, callback):
    handler.set_header('Content-Type', 'plain/text')
    handler.text = '1'
    callback()


def second_preprocessor(handler, callback):
    if handler.get_argument('fail', 'false') == 'true':
        raise HTTPError(503, 'error in preprocessor')
    else:
        handler.text += ' 2'
        callback()


def third_preprocessor(handler, callback):
    handler.text += ' 3'
    if handler.get_argument('nocallback', 'false') != 'true':
        callback()


def async_preprocessor(handler, callback):
    def _cb(data, response):
        handler.text += ' 4'
        callback()

    handler.post_url(handler.request.host + handler.request.path, callback=_cb)


@PageHandler.add_preprocessor
def preprocessor_as_decorator(handler, callback):
    handler.text += ' 5'
    callback()


class Page(PageHandler):
    preprocessors = (first_preprocessor, second_preprocessor, third_preprocessor)

    @PageHandler.add_preprocessor(async_preprocessor)
    @preprocessor_as_decorator
    def get_page(self):
        self.text += ' 6'

    def post_page(self):
        pass
