# -*- coding: utf-8 -*-
import lxml
import StringIO

class MockEmpInfo():
    def __init__(self,):
        self.condensed = 'emp(1),mng(3)'

class MockSession(object):
    def __init__(self,):
        self.site_id = 1
        self.lang = 'RU'
        self.condensed = 'type({type}),id({hhid})'.format(type='employer', hhid='1')
        self.empinfo = MockEmpInfo()

def pretty_print_xml(xml):
    parser = lxml.etree.XMLParser(remove_blank_text=True)
    tree = lxml.etree.parse(StringIO.StringIO(lxml.etree.tostring(xml)), parser)
    print lxml.etree.tostring(tree, pretty_print = True)

