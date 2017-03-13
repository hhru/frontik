# coding=utf-8

import os

from frontik.app import FileMappingDispatcher

from . import pages
from .pages import exception_on_prepare
from .pages import handler_404
from .pages import id_param
from .pages import simple

XML_root = None
XSL_root = os.path.normpath(os.path.join(os.path.dirname(__file__), 'xsl'))
XSL_cache_limit = 1

template_root = os.path.normpath(os.path.join(os.path.dirname(__file__), 'jinja'))

urls = [
    ('/id/(?P<id>[^/]+)', pages.id_param.Page),
    ('/id/(?P<id1>[^/]+)/(?P<id2>[^/]+)', pages.handler_404.Page, 'two_ids'),
    ('/not_simple', pages.simple.Page),
    ('/exception_on_prepare_regex', pages.exception_on_prepare.Page),
    ('(?!/not_matching_regex)', FileMappingDispatcher(pages, handler_404=pages.handler_404.Page))
]
