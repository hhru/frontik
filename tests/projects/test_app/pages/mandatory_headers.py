from tornado.web import HTTPError

from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):

        if self.get_argument('test_mandatory_headers', None) is not None:
            self.set_mandatory_header('TEST_HEADER', 'TEST_HEADER_VALUE')
            self.set_mandatory_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
            raise HTTPError(500)

        elif self.get_argument('test_without_mandatory_headers', None) is not None:
            self.add_header('TEST_HEADER', 'TEST_HEADER_VALUE')
            self.set_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
            raise HTTPError(500)

        elif self.get_argument('test_clear_set_mandatory_headers', None) is not None:
            self.set_mandatory_header('TEST_HEADER', 'TEST_HEADER_VALUE')
            self.set_mandatory_cookie('TEST_COOKIE', 'TEST_HEADER_COOKIE')
            self.clear_header('TEST_HEADER')
            self.clear_cookie('TEST_COOKIE')
            raise HTTPError(500)

        elif self.get_argument('test_clear_not_set_headers', None) is not None:
            self.clear_header('TEST_HEADER')
            self.clear_cookie('TEST_COOKIE')
            raise HTTPError(500)

        elif self.get_argument('test_invalid_mandatory_cookie') is not None:
            self.set_mandatory_cookie('TEST_COOKIE', '<!--#include file="/etc/passwd"-->')
            raise HTTPError(500)
