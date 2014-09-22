# coding=utf-8

import datetime
import json
import unittest

from tornado.concurrent import Future

from frontik.json_builder import JsonBuilder
from frontik.http_client import RequestResult, FailedRequestException


class TestJsonBuilder(unittest.TestCase):
    def test_simple(self):
        j = JsonBuilder()

        self.assertTrue(j.is_empty())
        self.assertEqual(j.to_string(), '{}')

        j.put({})
        self.assertFalse(j.is_empty())
        self.assertEqual(j.to_string(), '{}')

        j.put({'a': 'b'})

        self.assertFalse(j.is_empty())
        self.assertEqual(j.to_string(), """{"a": "b"}""")

    def test_clear(self):
        j = JsonBuilder()
        j.put({'a': 'b'})
        j.clear()

        self.assertTrue(j.is_empty())
        self.assertEqual(j.to_string(), '{}')

    def test_root_node_name(self):
        j = JsonBuilder(root_node='root')
        j.put({'a': 'b'})

        self.assertEqual(j.to_string(), """{"root": {"a": "b"}}""")

    def test_invalid_root_node_name(self):
        self.assertRaises(TypeError, JsonBuilder, root_node=10)

    def test_list(self):
        j = JsonBuilder()
        j.put({'a': {'b': [1, 2, 3]}})

        self.assertEqual(j.to_string(), """{"a": {"b": [1, 2, 3]}}""")

    def test_set(self):
        j = JsonBuilder()
        j.put({'a': {'b': {1, 2, 3}}})

        self.assertSetEqual(set(j.to_dict()['a']['b']), {1, 2, 3})

    def test_frozenset(self):
        j = JsonBuilder()
        j.put({'a': {'b': frozenset([1, 2, 3])}})

        self.assertSetEqual(set(j.to_dict()['a']['b']), {1, 2, 3})

    def test_date(self):
        j = JsonBuilder()
        j.put({'a': {'b': datetime.date(2000, 1, 2)}})

        self.assertEqual(j.to_string(), """{"a": {"b": "2000-01-02"}}""")

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

        j = JsonBuilder(json_encoder=JSONEncoder)
        j.put({'a': CustomValue()})

        self.assertEqual(j.to_string(), """{"a": "1.2.3"}""")

    def test_multiple_items(self):
        j = JsonBuilder()
        j.put({'a': 'b'})
        j.put({'c': 'd'})

        self.assertEqual(j.to_dict(), {'a': 'b', 'c': 'd'})

        j.put({'a': 'x'}, {'e': 'f'})

        self.assertEqual(j.to_dict(), {'a': 'x', 'c': 'd', 'e': 'f'})

        j.put(e='x')

        self.assertEqual(j.to_dict(), {'a': 'x', 'c': 'd', 'e': 'x'})

    def test_future(self):
        j = JsonBuilder()
        f = Future()
        j.put(f)

        self.assertFalse(j.is_empty())
        self.assertEqual(j.to_string(), """{}""")

        f.set_result({'a': 'b'})

        self.assertEqual(j.to_dict()['a'], 'b')
        self.assertEqual(j.to_string(), """{"a": "b"}""")

    def test_failed_future(self):
        j = JsonBuilder()
        f = Future()
        result = RequestResult()
        result.set_exception(FailedRequestException(reason='error', code='code'))
        f.set_result(result)
        j.put(f)

        self.assertEqual(j.to_dict(), {'error': {'reason': 'error', 'code': 'code'}})

    def test_nested_future(self):
        j = JsonBuilder()
        f1 = Future()
        f2 = Future()
        f3 = Future()

        f1.set_result({'nested': f2})
        j.put(f1)

        self.assertEqual(j.to_string(), """{"nested": null}""")

        f2.set_result({'a': f3})
        f3.set_result(['b', 'c'])

        self.assertEqual(j.to_string(), """{"nested": {"a": ["b", "c"]}}""")

    def test_nested_future_error_node(self):
        j = JsonBuilder()
        f1 = Future()
        f2 = Future()

        f1.set_result({'nested': f2})
        j.put(f1)

        self.assertEqual(j.to_string(), """{"nested": null}""")
        result = RequestResult()
        result.set_exception(FailedRequestException(reason='error', code='code'))

        f2.set_result(
            {'a': result}
        )

        self.assertEqual(
            j.to_dict(), {'nested': {'a': {'error': {'reason': 'error', 'code': 'code'}}}}
        )

    def test_nested_json_builder(self):
        j1 = JsonBuilder()
        j1.put(k1='v1')

        j2 = JsonBuilder()
        j2.put(k2='v2')

        j1.put(j2)

        self.assertEqual(
            j1.to_dict(), {'k2': 'v2', 'k1': 'v1'}
        )

    def test_dict_put_invalid(self):
        j = JsonBuilder()
        j.put({'a': 'b'})
        j.put(['c'])

        self.assertRaises(ValueError, j.to_dict)

    def test_to_dict(self):
        class Serializable(object):
            def __init__(self, name, values):
                self.name = name
                self.values = values

            def to_dict(self):
                return {self.name: self.values}

        j = JsonBuilder()
        j.put(Serializable('some', ['test1', 'test2', 'test3']))

        self.assertEqual(
            j.to_dict(), {'some': ['test1', 'test2', 'test3']}
        )

    def test_to_json_value(self):
        class SomeObj(object):
            def __init__(self, val):
                self.val = val

            def to_json_value(self):
                return [self.val]

        j = JsonBuilder()
        j.put({'1': SomeObj(1)})
        j.put({'2': SomeObj('2')})
        j.put({'3': SomeObj(frozenset([3]))})

        self.assertEqual(
            j.to_dict(), {'1': [1], '2': ['2'], '3': [[3]]}
        )
