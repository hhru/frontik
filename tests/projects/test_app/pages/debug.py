import logging

from fastapi import Request
from lxml.builder import E

from frontik import media_types
from frontik.balancing_client import HttpClientT
from frontik.handler import PageHandler, get_current_handler
from frontik.routing import plain_router, router

logger = logging.getLogger('handler')


@router.get('/debug_asgi')
async def get_page_asgi(http_client: HttpClientT, request: Request, no_recursion: str = 'false') -> None:
    logger.debug('debug: starting debug page')

    def _exception_trace() -> None:
        def _inner() -> None:
            msg = 'Testing an exception юникод'
            raise ValueError(msg)

        _inner()

    try:
        _exception_trace()
    except ValueError:
        logger.exception('exception catched')

    logger.warning('warning: testing simple inherited debug')
    await http_client.post_url(request.headers.get('host', 'no_host'), '/debug')

    logger.error('error: testing failing urls')
    await http_client.get_url('invalid_host', 'invalid_url')

    logger.info('info: testing responses')
    await http_client.put_url(request.headers.get('host', 'no_host'), 'debug?type=html')
    await http_client.put_url(request.headers.get('host', 'no_host'), 'debug?type=protobuf')
    await http_client.put_url(request.headers.get('host', 'no_host'), 'debug?type=xml')
    await http_client.put_url(request.headers.get('host', 'no_host'), 'debug?type=javascript')
    await http_client.put_url(request.headers.get('host', 'no_host'), 'debug?type=text')

    logger.debug('testing xml output', extra={'_xml': E.root(E.child1(param='тест'), E.child2('тест'))})
    logger.debug('testing utf-8 text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})
    logger.debug('testing unicode text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})

    if no_recursion != 'true':
        logger.debug('testing complex inherited debug')
        await http_client.get_url(request.headers.get('host', 'no_host'), 'debug?no_recursion=true&debug=xslt')


@plain_router.get('/debug', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    handler.log.debug('debug: starting debug page')

    def _exception_trace() -> None:
        def _inner() -> None:
            msg = 'Testing an exception юникод'
            raise ValueError(msg)

        _inner()

    try:
        _exception_trace()
    except ValueError:
        handler.log.exception('exception catched')

    handler.log.warning('warning: testing simple inherited debug')
    await handler.post_url(handler.get_header('host', 'no_host'), handler.path)

    handler.log.error('error: testing failing urls')
    await handler.get_url('invalid_host', 'invalid_url')

    handler.log.info('info: testing responses')
    await handler.put_url(handler.get_header('host', 'no_host'), handler.path + '?type=html')
    await handler.put_url(handler.get_header('host', 'no_host'), handler.path + '?type=protobuf')
    await handler.put_url(handler.get_header('host', 'no_host'), handler.path + '?type=xml')
    await handler.put_url(handler.get_header('host', 'no_host'), handler.path + '?type=javascript')
    await handler.put_url(handler.get_header('host', 'no_host'), handler.path + '?type=text')

    if handler.get_query_argument('no_recursion', 'false') != 'true':
        handler.log.debug('testing complex inherited debug')
        await handler.get_url(handler.get_header('host', 'no_host'), handler.path + '?no_recursion=true&debug=xslt')
    else:
        handler.log.debug('testing xslt profiling')
        handler.set_xsl('simple.xsl')

    handler.log.debug('testing xml output', extra={'_xml': E.root(E.child1(param='тест'), E.child2('тест'))})
    handler.log.debug('testing utf-8 text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})
    handler.log.debug('testing unicode text output', extra={'_text': 'some\nmultiline\nюникод\ndebug'})


@plain_router.post('/debug', cls=PageHandler)
async def post_page(handler: PageHandler = get_current_handler()) -> None:
    handler.log.debug('this page returns json')

    handler.json.put({'param1': 'value', 'param2': 'тест', 'тест': 'value'})


@plain_router.put('/debug', cls=PageHandler)
async def put_page(handler: PageHandler = get_current_handler()) -> None:
    content_type = handler.get_query_argument('type')

    if content_type == 'html':
        handler.set_header('Content-Type', media_types.TEXT_HTML)
        handler.text = '<html><h1>ok</h1></html>'
    elif content_type == 'protobuf':
        handler.set_header('Content-Type', media_types.APPLICATION_PROTOBUF)
        handler.text = 'SomeProtobufObject()'
    elif content_type == 'xml':
        handler.doc.put(E.response('some xml'))
    elif content_type == 'javascript':
        handler.set_header('Content-Type', media_types.APPLICATION_JAVASCRIPT)
        handler.text = 'document.body.write("Привет")'
    elif content_type == 'text':
        handler.set_header('Content-Type', media_types.TEXT_PLAIN)
        handler.text = 'привет charset'.encode()
