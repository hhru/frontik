# coding=utf-8

from frontik.routing import FileMappingRouter

from . import pages
from .pages import handler_404
from .pages import id_param
from .pages import simple

urls = [
    ('/id/(?P<id>[^/]+)', id_param.Page),
    ('/id/(?P<id1>[^/]+)/(?P<id2>[^/]+)', handler_404.Page, 'two_ids'),
    ('/not_simple', simple.Page),
    ('(?!/not_matching_regex)', FileMappingRouter(pages))
]
