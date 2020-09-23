from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


def add_params(name):
    @preprocessor
    def pp(handler):
        param_value = handler.get_argument(name, None)
        if param_value:
            handler.add_page_handler_param(name, param_value)

    return pp


class Page(PageHandler):

    @add_params('param1')
    @add_params('param2')
    def get_page(self, param1, param2='param2_default'):
        self.json.put({
            'param1': param1,
            'param2': param2,
        })
