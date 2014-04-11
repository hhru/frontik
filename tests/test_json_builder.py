import json
import unittest

import frontik.future
import frontik.json_builder


class TestDoc(unittest.TestCase):
    def test_simple(self):
        j = frontik.json_builder.JsonBuilder()

        self.assertTrue(j.is_empty())

        j.put({'a': 'b'})

        self.assertFalse(j.is_empty())
        self.assertEqual(j.to_string(), """{"a": "b"}""")

    def test_root_node_name(self):
        j = frontik.json_builder.JsonBuilder(root_node_name='root')
        j.put({'a': 'b'})

        self.assertEqual(j.to_string(), """{"root": {"a": "b"}}""")

    def test_list(self):
        j = frontik.json_builder.JsonBuilder()
        j.put({'a': {'b': [1, 2, 3]}})

        self.assertEqual(j.to_string(), """{"a": {"b": [1, 2, 3]}}""")

    def test_encoder(self):
        class CustomValue(object):
            def __iter__(self):
                return iter((1, 2, 3))

            def to_json(self):
                return '1.2.3'

        class JSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if hasattr(obj, 'to_json'):
                    return obj.to_json()
                return json.JSONEncoder.default(self, obj)

        j = frontik.json_builder.JsonBuilder(json_encoder=JSONEncoder)
        j.put({'a': CustomValue()})

        self.assertEqual(j.to_string(), """{"a": "1.2.3"}""")

    def test_multiple_items(self):
        j = frontik.json_builder.JsonBuilder()
        j.put({'a': 'b'})
        j.put({'c': 'd'})

        self.assertEqual(j.to_string(), """{"a": "b", "c": "d"}""")

        j.put({'a': 'x'}, {'e': 'f'})

        self.assertEqual(j.to_string(), """{"a": "x", "c": "d", "e": "f"}""")

        j.put(e='x')

        self.assertEqual(j.to_string(), """{"a": "x", "c": "d", "e": "x"}""")

    def test_placeholder(self):
        j = frontik.json_builder.JsonBuilder()
        p = frontik.future.Placeholder()
        j.put(p)

        self.assertFalse(j.is_empty())
        self.assertEqual(j.to_string(), """{}""")

        p.set_data({'a': 'b'})

        self.assertEqual(j.to_dict()['a'], 'b')
        self.assertEqual(j.to_string(), """{"a": "b"}""")

    def test_failed_future(self):
        j = frontik.json_builder.JsonBuilder()
        p = frontik.future.Placeholder()
        p.set_data(frontik.future.FailedFutureException(error='error', code='code', body='body'))
        j.put(p)

        self.assertEqual(j.to_string(), """{"error": {"reason": "error", "code": "code"}}""")

    def test_nested_future(self):
        j = frontik.json_builder.JsonBuilder()
        p1 = frontik.future.Placeholder()
        p2 = frontik.future.Placeholder()
        p3 = frontik.future.Placeholder()

        p1.set_data({'nested': p2})
        j.put(p1)

        self.assertEqual(j.to_string(), """{"nested": null}""")

        p2.set_data({'a': p3})
        p3.set_data(['b', 'c'])

        self.assertEqual(j.to_string(), """{"nested": {"a": ["b", "c"]}}""")

        p2.set_data(
            {'a': frontik.future.FailedFutureException(error='error', code='code', body='body')}
        )

        self.assertEqual(
            j.to_string(), """{"nested": {"a": {"error": {"reason": "error", "code": "code"}}}}"""
        )

    def test_nested_json_builder(self):
        j1 = frontik.json_builder.JsonBuilder()
        j1.put(k1='v1')

        j2 = frontik.json_builder.JsonBuilder()
        j2.put(k2='v2')

        j1.put(j2)

        self.assertEqual(
            j1.to_string(), """{"k2": "v2", "k1": "v1"}"""
        )

    def test_dict_put_invalid(self):
        j = frontik.json_builder.JsonBuilder()
        j.put({'a': 'b'})
        j.put(['c'])

        self.assertRaises(ValueError, j.to_dict)


if __name__ == '__main__':
    unittest.main()
