from frontik.handler import PageHandler
from frontik.preprocessors import preprocessor


@preprocessor
def pp0(handler):
    pass


@preprocessor
def pp1(handler):
    pass


@preprocessor
def pp2(handler):
    pass


@preprocessor
def pp3(handler):
    pass


class Page(PageHandler):
    preprocessors = [pp0]

    @pp1
    @pp2
    async def get_page(self):
        self.json.put(
            {
                'pp0': self.was_preprocessor_called(pp0),
                'pp1': self.was_preprocessor_called(pp1),
                'pp2': self.was_preprocessor_called(pp2),
                'pp3': self.was_preprocessor_called(pp3),
            },
        )
