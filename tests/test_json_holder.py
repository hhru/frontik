import unittest
from functools import partial

import frontik.future
import frontik.json_holder


class TestDoc(unittest.TestCase):
    def test_simple(self):
        j = frontik.json_holder.JsonHolder()

        self.assertTrue(j.is_empty())

        j.put({'a': 'b'})

        self.assertFalse(j.is_empty())
        self.assertEqual(j.to_string(), """{"a": "b"}""")

    def test_multiple_items(self):
        j = frontik.json_holder.JsonHolder()
        j.put({'a': 'b'})
        j.put({'c': 'd'})

        self.assertEqual(j.to_string(), """{"a": "b", "c": "d"}""")

        j.put({'a': 'x'})

        self.assertEqual(j.to_string(), """{"a": "x", "c": "d"}""")

    def test_placeholder(self):
        j = frontik.json_holder.JsonHolder()
        p = frontik.future.Placeholder()
        j.put(p)

        self.assertFalse(j.is_empty())
        self.assertEqual(j.to_string(), """{}""")

        p.set_data({'a': 'b'})

        self.assertEqual(j.to_string(), """{"a": "b"}""")

    def test_failed_future(self):
        j = frontik.json_holder.JsonHolder()
        p = frontik.future.Placeholder()
        p.set_data(frontik.future.FailedFutureException(effective_url='url', error='error', code='code', body='body'))
        j.put(p)

        self.assertEqual(j.to_string(), """{"error": {"url": "url", "reason": "error", "code": "code"}}""")

    def test_nested(self):
        j = frontik.json_holder.JsonHolder()
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
            {'a': frontik.future.FailedFutureException(effective_url='url', error='error', code='code', body='body')}
        )

        self.assertEqual(
            j.to_string(), """{"nested": {"a": {"error": {"url": "url", "reason": "error", "code": "code"}}}}"""
        )

    def test_list_mode(self):
        j = frontik.json_holder.JsonHolder()
        j.put(['a', 'b'])

        self.assertEqual(j.to_string(), """["a", "b"]""")

        j.put(['c', 'd'])

        self.assertEqual(j.to_string(), """["a", "b", "c", "d"]""")

        j.put('f', key_name='e')

        self.assertEqual(j.to_string(), """["a", "b", "c", "d", {"e": "f"}]""")

    def test_invalid(self):
        j = frontik.json_holder.JsonHolder()
        j.put({'a': 'b'})

        self.assertRaises(ValueError, partial(j.put, ['c']))


if __name__ == '__main__':
    unittest.main()
