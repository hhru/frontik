# -*- coding: utf-8 -*-

# etree - модуль, который используется как реализация ElementTree
import lxml.etree as etree
from lxml.builder import E as etree_builder

# Doc класс для формирования XML-ответа
from frontik.doc import Doc
from frontik.util import list_unique
from frontik.util import make_qs
from frontik.util import make_url

#from frontik.handler import PageHandler
