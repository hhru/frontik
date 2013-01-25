import os

XSL_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "xsl"))
XML_root = None
apply_xsl = True

def post(self, data, cb):
    self.log.debug('posprocessor called')
    cb(data)
    
postprocessor = post

XSL_cache_limit = 1

from frontik.app import Map2ModuleName
frontik_import("pages")
frontik_import("pages.simple")
frontik_import("pages.id_param")

urls=[
        ("/+id/+(?P<id>[^/]+)", pages.id_param.Page),
        ("/+ids/+(?P<id>[^/]+)", pages.id_param.Page, lambda x: x.split(',')),
        ("/+not_simple", pages.simple.Page),
        ("", Map2ModuleName(pages)),
]