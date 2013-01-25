# -*- coding: utf-8 -*-

from frontik.version import version

__version__ = VERSION = version
import lxml.etree as etree
from lxml.builder import E as etree_builder

from frontik.doc import Doc
from frontik.util import make_url
from frontik.util import list_unique
from frontik.util import make_qs
