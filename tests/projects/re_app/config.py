# coding=utf-8

import os

from frontik.app import FileMappingDispatcher

from . import pages
from .pages import exception_on_init
from .pages import handler_404
from .pages import id_param
from .pages import simple

XML_root = None
XSL_root = os.path.normpath(os.path.join(os.path.dirname(__file__), 'xsl'))
XSL_cache_limit = 1

urls = [
    ('/id/(?P<id>[^/]+)', pages.id_param.Page),
    ('/not_simple', pages.simple.Page),
    ('/fail_on_init', pages.exception_on_init.Page),
    ('(?!/not_matching_regex)', FileMappingDispatcher(pages, handler_404=pages.handler_404.Page))
]
