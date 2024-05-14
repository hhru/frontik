from tornado.escape import to_unicode

from frontik.util import make_url
from tests.instances import frontik_test_app


class TestUnicode:
    def test_unicode_argument(self):
        response = frontik_test_app.get_page(make_url('arguments', param='тест'))
        assert response.status_code == 200
        assert to_unicode(response.content) == '{"тест":"тест"}'

    def test_cp1251_argument(self):
        cp1251_arg = 'тест'.encode('cp1251')
        response = frontik_test_app.get_page(make_url('arguments?enc=true', param=cp1251_arg))

        assert response.status_code == 200
        assert to_unicode(response.content) == '{"тест":"тест"}'

    def test_argument_with_invalid_chars(self):
        arg_with_invalid_chars = '≤'.encode('koi8_r') + 'тест'.encode()
        response = frontik_test_app.get_page(make_url('arguments?enc=true', param=arg_with_invalid_chars))

        assert response.status_code == 200
        assert to_unicode(response.content) == '{"тест":"тест"}'
