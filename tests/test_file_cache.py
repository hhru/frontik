import logging
import os
import unittest
from functools import partial

from frontik.file_cache import FileCache, LimitedDict


class TestFileCache(unittest.TestCase):
    def test_limited_dict(self):
        d = LimitedDict(max_len=3)

        d[1] = 1
        d[2] = 2
        d[3] = 3

        self.assertEqual(len(d), 3)

        d[4] = 4

        self.assertEqual(len(d), 3)
        self.assertNotIn(1, d)

        t = d[2] + 3  # access the oldest item
        d[5] = t  # then try to evict it

        self.assertEqual(len(d), 3)
        self.assertIn(2, d)

    def test_limited_dict_with_step(self):
        d = LimitedDict(max_len=10, step=3)

        for i in range(10):
            d[i] = i

        d[10] = 10

        self.assertEqual(len(d), 10)
        self.assertNotIn(0, d)

        t = d[1] + 10  # access the oldest item
        d[11] = t  # then try to evict it

        self.assertEqual(len(d), 10)
        self.assertIn(1, d)

    def test_unlimited_dict(self):
        d = LimitedDict()

        for i in range(10):
            d[i] = i

        for i in range(10):
            self.assertEqual(d[i], i)

    CACHE_DIR = os.path.join(os.path.dirname(__file__), 'projects', 'test_app', 'xsl')

    class MockLog(logging.Logger):
        def __init__(self) -> None:
            self.message: str
            self.level = 0
            self.parent = None
            self.name = 'mock_logger'

        def debug(self, message, *args):
            self.message = message % args

        def info(self, message, *args):
            self.message = message % args

    def test_file_cache(self):
        c = FileCache('test', self.CACHE_DIR, lambda filename, log: filename, max_len=3)
        log = TestFileCache.MockLog()

        c.load('simple.xsl', log)

        self.assertEqual(len(c.cache), 1)
        self.assertIn('reading file', log.message)

        c.load('parse_error.xsl', log)
        c.load('syntax_error.xsl', log)
        c.load('simple.xsl', log)

        self.assertIn('got simple.xsl file from cache (test cache size: 3)', log.message)

        c.load('apply_error.xsl', log)
        self.assertEqual(len(c.cache), 3)

        c.load('parse_error.xsl', log)
        self.assertIn('reading file', log.message)

    def test_populate(self):
        c = FileCache('test', self.CACHE_DIR, lambda filename, log: filename, max_len=3)
        log = TestFileCache.MockLog()

        c.populate(['simple.xsl', 'parse_error.xsl', 'syntax_error.xsl'], log)

        self.assertEqual(len(c.cache), 3)

        c.load('apply_error.xsl', log)
        self.assertIn('reading file', log.message)

    def test_populate_and_freeze(self):
        c = FileCache('test', self.CACHE_DIR, lambda filename, log: filename, max_len=None)
        log = TestFileCache.MockLog()

        c.populate(['simple.xsl', 'parse_error.xsl', 'simple.xsl'], log, freeze=True)

        self.assertRaises(Exception, partial(c.load, 'apply_error.xsl', log))
