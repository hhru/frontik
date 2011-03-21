# -*- coding: utf-8 -*-

VERSION = (2, 8, 0, "final")

def get_version():
    if VERSION[3] != "final":
        return "%s.%s.%s%s" % (VERSION[0], VERSION[1], VERSION[2], VERSION[3])
    else:
        return "%s.%s.%s" % (VERSION[0], VERSION[1], VERSION[2])

__version__ = get_version()

import lxml.etree as etree
from lxml.builder import E as etree_builder

from frontik.doc import Doc
from frontik.util import make_url
from frontik.util import list_unique
from frontik.util import make_qs
