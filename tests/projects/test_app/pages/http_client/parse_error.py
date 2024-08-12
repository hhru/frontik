from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router


@plain_router.get('/http_client/parse_error', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    el_result = await handler.post_url(handler.get_header('host'), handler.path + '?mode=xml')
    element = el_result.data
    if element is None:
        handler.text = 'Parse error occured'
    else:
        raise AssertionError()

    result = await handler.post_url(handler.get_header('host'), handler.path + '?mode=json')
    if result.failed:
        handler.text = 'Parse error occured'
    else:
        raise AssertionError()


@plain_router.post('/http_client/parse_error', cls=PageHandler)
async def post_page(handler=get_current_handler()):
    if handler.get_query_argument('mode') == 'xml':
        handler.text = """<doc frontik="tr"ue">this is broken xml</doc>"""
        handler.set_header('Content-Type', 'xml')
    elif handler.get_query_argument('mode') == 'json':
        handler.text = """{"hel"lo" : "this is broken json"}"""
        handler.set_header('Content-Type', 'json')
