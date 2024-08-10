from frontik import media_types
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router
from frontik.util import gather_dict


class Page(PageHandler):
    def prepare(self):
        if self.get_query_argument('custom_render', 'false') == 'true':

            def jinja_context_provider(handler):
                return {'req1': {'result': 'custom1'}, 'req2': {'result': 'custom2'}}

            self.jinja_context_provider = jinja_context_provider

        super().prepare()


@plain_router.get('/json_page', cls=Page)
async def get_page(handler: Page = get_current_handler()) -> None:
    invalid_json = handler.get_query_argument('invalid', 'false')

    requests = {
        'req1': handler.post_url(handler.request.headers.get('host', ''), handler.path, data={'param': 1}),
        'req2': handler.post_url(
            handler.request.headers.get('host', ''), handler.path, data={'param': 2, 'invalid': invalid_json}
        ),
    }
    data = await gather_dict(requests)

    if handler.get_query_argument('template_error', 'false') == 'true':
        del data['req1']

    handler.set_template(handler.get_query_argument('template', 'jinja.html'))  # type: ignore
    handler.json.put(data)


@plain_router.post('/json_page', cls=Page)
async def post_page(handler=get_current_handler()):
    invalid_json = handler.get_body_argument('invalid', 'false') == 'true'

    if not invalid_json:
        handler.json.put({'result': handler.get_body_argument('param')})
    else:
        handler.set_header('Content-Type', media_types.APPLICATION_JSON)
        handler.text = '{"result": FAIL}'
