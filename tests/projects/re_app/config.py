from frontik.routing import FileMappingRouter

from tests.projects.re_app import pages
from tests.projects.re_app.pages import handler_404
from tests.projects.re_app.pages import id_param
from tests.projects.re_app.pages import simple

urls = [
    ('/id/(?P<id>[^/]+)', id_param.Page),
    ('/id/(?P<id1>[^/]+)/(?P<id2>[^/]+)', handler_404.Page, 'two_ids'),
    ('/not_simple', simple.Page),
    ('(?!/not_matching_regex)', FileMappingRouter(pages))
]
