from tornado.web import HTTPError

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


@router.get('/mandatory_headers', cls=PageHandler)
async def get_page(handler=get_current_handler()):
    if handler.get_argument('test_mandatory_headers', None) is not None:
        handler.set_mandatory_header('TEST_HEADER', 'TEST_HEADER_VALUE')
        handler.set_mandatory_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
        raise HTTPError(500)

    elif handler.get_argument('test_without_mandatory_headers', None) is not None:
        handler.add_header('TEST_HEADER', 'TEST_HEADER_VALUE')
        handler.set_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
        raise HTTPError(500)

    elif handler.get_argument('test_clear_set_mandatory_headers', None) is not None:
        handler.set_mandatory_header('TEST_HEADER', 'TEST_HEADER_VALUE')
        handler.set_mandatory_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
        handler.clear_header('TEST_HEADER')
        handler.clear_cookie('TEST_COOKIE')
        raise HTTPError(500)

    elif handler.get_argument('test_clear_not_set_headers', None) is not None:
        handler.clear_header('TEST_HEADER')
        handler.clear_cookie('TEST_COOKIE')
        raise HTTPError(500)

    elif handler.get_argument('test_invalid_mandatory_cookie') is not None:
        handler.set_mandatory_cookie('TEST_COOKIE', '<!--#include file="/etc/passwd"-->')
        raise HTTPError(500)
