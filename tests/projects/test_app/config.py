# coding=utf-8

import os

from lxml import etree

XSL_root = os.path.normpath(os.path.join(os.path.dirname(__file__), 'xsl'))
XML_root = os.path.normpath(os.path.join(os.path.dirname(__file__), 'xml'))
template_root = os.path.normpath(os.path.join(os.path.dirname(__file__), 'templates'))

XSL_cache_limit = 1
XML_cache_step = 1

version = [etree.Element('app-version', number='last version')]

debug_labels = {
    'test': '#f88',
    u'ТЕСТ': '#88f'
}
