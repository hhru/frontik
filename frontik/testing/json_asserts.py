# coding=utf-8

import types

from tornado.escape import recursive_unicode


def _is_json_scalar_type(val):
    return isinstance(val, (unicode, str, bool, int, float, long, types.NoneType))


def _is_json_non_scalar_type(val):
    return isinstance(val, (list, dict))


def _is_json_key_type(val):
    return isinstance(val, (unicode, str))


class JsonTestCaseMixin(object):
    """Mixin for unittest.TestCase that adds json-like python structures asserts."""

    def _assertIsJsonKeyType(self, val, msg=None):
        self.assertTrue(_is_json_key_type(val), msg)

    def _assertIsJsonValueType(self, val, msg=None):
        self.assertTrue(_is_json_scalar_type(val) or _is_json_non_scalar_type(val), msg)

    def _format_msg_and_path(self, string, msg, path):
        return '{msg}{path} - {string}'.format(
            msg=msg + ': ' if msg is not None else '',
            path=path if path != '' else '<ROOT>',
            string=string
        )

    def _assertIsJson(self, data, path='', msg=None):
        if isinstance(data, list):
            for i, list_item in enumerate(data):
                self._assertIsJson(list_item, path + '[{}]'.format(i), msg)

        elif isinstance(data, dict):
            for key, dict_item in data.iteritems():
                self._assertIsJsonKeyType(
                    key, self._format_msg_and_path('Wrong key type ({!r})'.format(key), msg, path)
                )

                self._assertIsJson(dict_item, '.'.join(filter(None, (path, key))), msg)

        else:
            self._assertIsJsonValueType(
                data, self._format_msg_and_path('Wrong value type ({!r})'.format(type(data)), msg, path)
            )

    def _assertJsonStructuresEqualsRecursive(self, a, b, path, msg):
        a_type = unicode if type(a) == str else type(a)
        b_type = unicode if type(b) == str else type(b)

        self.assertEqual(
            a_type, b_type,
            self._format_msg_and_path('Types are not equal: {} != {}'.format(type(a), type(b)), msg, path)
        )

        if isinstance(a, list):
            self.assertEqual(
                len(a), len(b),
                self._format_msg_and_path('Lists lengths are not equal: {} != {}'.format(len(a), len(b)), msg, path)
            )

            for i in xrange(len(a)):
                self._assertJsonStructuresEqualsRecursive(a[i], b[i], path + '[{}]'.format(i), msg)

        elif isinstance(a, dict):
            a_keys = sorted(a.keys())
            b_keys = sorted(b.keys())

            self.assertEqual(
                a_keys, b_keys,
                self._format_msg_and_path('Dict keys are not equal: {} != {}'.format(a_keys, b_keys), msg, path)
            )

            for key in a_keys:
                self._assertJsonStructuresEqualsRecursive(a[key], b[key], '.'.join(filter(None, (path, key))), msg)

        else:
            self.assertEqual(
                recursive_unicode(a), recursive_unicode(b),
                self._format_msg_and_path('Values are not equal: {!r} != {!r}'.format(a, b), msg, path)
            )

    def assertIsJson(self, data, msg=None):
        self._assertIsJson(data, '', msg)

    def assertJsonEqual(self, a, b, msg=None):
        msg_prefix = msg if msg is not None else '{}: '.format(msg)
        self._assertIsJson(a, msg='{}Wrong first structure'.format(msg_prefix))
        self._assertIsJson(b, msg='{}Wrong second structure'.format(msg_prefix))
        self._assertJsonStructuresEqualsRecursive(a, b, '', msg)
