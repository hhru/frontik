# coding=utf-8

from frontik.routing import FileMappingRouter

from . import pages
from .pages import exception_on_prepare
from .pages import handler_404
from .pages import id_param
from .pages import simple

urls = [
    ('/id/(?P<id>[^/]+)', id_param.Page),
    ('/id/(?P<id1>[^/]+)/(?P<id2>[^/]+)', handler_404.Page, 'two_ids'),
    ('/not_simple', simple.Page),
    ('/exception_on_prepare_regex', exception_on_prepare.Page),
    ('(?!/not_matching_regex)', FileMappingRouter(pages))
]
