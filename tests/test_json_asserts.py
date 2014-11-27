# coding=utf-8

import unittest
import datetime

from frontik.testing import json_asserts


class AssertsTestCase(unittest.TestCase, json_asserts.JsonTestCaseMixin):

    def test_assert_is_json(self):
        good_json = (
            {'a': '13', 'b': {'error': 'hmm', 'msgs': ['a', 'b', None]}},
            [{'id': 5, 'name': 'five'}, {'id': 6, 'name': 'six'}],
            [{'int': 1}, {'float': 3.4}, {'long': 10L}, {'bool': True}, {'null': None}]
        )

        for json in good_json:
            try:
                self.assertIsJson(json)
            except AssertionError:
                self.fail('Structure {!r} should not fail assertion'.format(json))

    def test_assert_is_not_json(self):
        bad_json = (
            object(),
            datetime.datetime.now(),
            (1 + 2j),  # complex
            {None: '123'},
            {datetime.datetime.now(): '123'},
        )

        for json in bad_json:
            self.assertRaises(AssertionError, self.assertIsJson, json)

    def test_assert_is_json_message_dict(self):
        json = {
            'a': [
                1, {'b': object()}
            ]
        }

        try:
            self.assertIsJson(json, msg='Pre words')
            self.fail('AssertionError must be raised')
        except AssertionError as e:
            self.assertEqual(e.args[0], "Pre words: a[1].b - Wrong value type (<type 'object'>)")

    def test_assert_is_json_message_array(self):
        json = [1, 'bb', {'b': object()}]

        try:
            self.assertIsJson(json, msg='Pre words')
            self.fail('AssertionError must be raised')
        except AssertionError as e:
            self.assertEquals(e.args[0], "Pre words: [2].b - Wrong value type (<type 'object'>)")

    def test_assert_is_json_message_for_root(self):
        try:
            self.assertIsJson(object(), 'Pre words')
            self.fail('AssertionError must be raised')
        except AssertionError as e:
            self.assertEquals(e.args[0], "Pre words: <ROOT> - Wrong value type (<type 'object'>)")

    def test_assert_is_json_message_key_type(self):
        try:
            self.assertIsJson({'val': [{None: '123'}]}, 'Pre words')
            self.fail('AssertionError must be raised')
        except AssertionError as e:
            self.assertEquals(e.args[0], 'Pre words: val[0] - Wrong key type (None)')

    def test_assert_json_equal(self):
        equal_json = (
            (
                {
                    'b': 5,
                    'c': 3,
                    'd': ['23', {}],
                    'e': [],
                },
                {
                    'e': [],
                    'c': 3,
                    'b': 5,
                    'd': ['23', {}],
                }
            ),
            ('ascii', u'ascii'),
            ('русский', u'русский'),
            ([], []),
            ({}, {}),
            (None, None),
            ([1, 2, {'a': 5}], [1, 2, {u'a': 5}]),
        )

        for a, b in equal_json:
            self.assertJsonEqual(a, b)

    def test_assert_json_not_equal(self):
        not_equal_json = (
            ([5], ['5']),
            ([None], ['']),
            ([{'a': 5, 'b': 3}], [{'a': 5, 'b': 3, 'c': 4}]),
        )

        for a, b in not_equal_json:
            self.assertRaises(AssertionError, self.assertJsonEqual, a, b)

    def test_assert_json_equal_keys_not_equal_message(self):
        try:
            self.assertJsonEqual({'a': '1', 'b': '2'}, {'a': '1', 'b': '2', 'c': '3'}, 'Pre words')
            self.fail('AssertionError must be raised')
        except AssertionError as e:
            self.assertEquals(e.args[0], "Pre words: <ROOT> - Dict keys are not equal: ['a', 'b'] != ['a', 'b', 'c']")

    def test_assert_json_equal_values_not_equal_message(self):
        try:
            self.assertJsonEqual([{'a': '1', 'b': '2'}], [{'a': '1', 'b': u'333'}], 'Pre words')
            self.fail('AssertionError must be raised')
        except AssertionError as e:
            self.assertEquals(e.args[0], "Pre words: [0].b - Values are not equal: '2' != u'333'")

    def test_assert_json_equal_types_not_equal_message(self):
        try:
            self.assertJsonEqual([{'a': '1', 'b': '2'}], [{'a': '1', 'b': {'hm': 'oh-no'}}], 'Pre words')
            self.fail('AssertionError must be raised')
        except AssertionError as e:
            self.assertEquals(e.args[0], "Pre words: [0].b - Types are not equal: <type 'str'> != <type 'dict'>")
