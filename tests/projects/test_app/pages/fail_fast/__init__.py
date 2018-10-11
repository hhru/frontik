from frontik.handler import HTTPErrorWithPostprocessors, PageHandler
from frontik.preprocessors import preprocessor


@preprocessor
def get_page_preprocessor(handler):
    handler.json.put({
        'preprocessor': True
    })


class Page(PageHandler):
    @get_page_preprocessor
    def get_page(self):
        fail_fast = self.get_argument('fail_fast', 'false') == 'true'

        if self.get_argument('return_none', 'false') == 'true':
            return

        results = yield {
            'get': self.get_url(self.request.host, self.request.path, data={'return_none': 'true'}, fail_fast=True),
            'post': self.post_url(self.request.host, self.request.path, data={'param': 'post'}),
            'put': self.put_url(
                self.request.host, self.request.path + '?code=401', fail_fast=fail_fast, parse_on_error=True
            ),
            'delete': self.delete_url(self.request.host, self.request.path, data={'invalid_dict_value': 'true'}),
        }

        assert results['post'].response.code == 200
        assert results['put'].response.code == 401
        assert results['delete'].response.code == 500

        self.json.put(results)

    def get_page_fail_fast(self, failed_future):
        if self.get_argument('exception_in_fail_fast', 'false') == 'true':
            raise Exception('Exception in fail_fast')

        self.json.replace({'fail_fast': True})
        self.set_status(403)
        self.finish_with_postprocessors()

    def post_page(self):
        if self.get_argument('fail_fast_default', 'false') == 'true':
            results = yield {
                'e': self.put_url(
                    self.request.host, '{}?code={}'.format(self.request.path, self.get_argument('code')),
                    fail_fast=True
                )
            }

            self.json.put(results)
        else:
            self.json.put({
                'POST': self.get_argument('param')
            })

    def put_page(self):
        # Testing parse_on_error=True
        self.json.put({'error': 'forbidden'})
        raise HTTPErrorWithPostprocessors(int(self.get_argument('code')))

    def delete_page(self):
        # Testing invalid return values
        if self.get_argument('invalid_dict_value', 'false') == 'true':
            yield {'invalid': 'value'}
