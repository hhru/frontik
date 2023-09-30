from frontik.handler import PageHandler
from frontik.preprocessors import make_preprocessors_names_list, preprocessor


@preprocessor
def pp0(handler):
    handler.called_preprocessors = ['pp0']


@preprocessor
def pp1(handler):
    handler.called_preprocessors.append('pp1')


@preprocessor
def pp2(handler):
    handler.called_preprocessors.append('pp2')


@preprocessor
def pp3(handler):
    handler.called_preprocessors.append('pp3')


class Page(PageHandler):
    preprocessors = [pp0]
    _priority_preprocessor_names = make_preprocessors_names_list([pp2, pp1])

    @pp1
    @pp3
    @pp2
    async def get_page(self):
        self.json.put(
            {
                'order': self.called_preprocessors,  # type: ignore
            },
        )
