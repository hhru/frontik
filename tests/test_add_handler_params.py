import unittest

from .instances import frontik_test_app


class TestAddPageHandlerParams(unittest.TestCase):
    def test_add_page_handler_params_with_default(self):
        response_json = frontik_test_app.get_page_json('preprocessors/add_page_handler_params?param1=value')
        self.assertEqual(
            response_json,
            {
                'param1': 'value',
                'param2': 'param2_default'
            }
        )

    def test_add_page_handler_params_without_default(self):
        response_json = frontik_test_app.get_page_json(
            'preprocessors/add_page_handler_params?param1=value1&param2=value2'
        )
        self.assertEqual(
            response_json,
            {
                'param1': 'value1',
                'param2': 'value2'
            }
        )
