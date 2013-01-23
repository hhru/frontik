# -*- coding: utf-8 -*-
import lxml
import StringIO

def pretty_print_xml(xml):
    parser = lxml.etree.XMLParser(remove_blank_text=True)
    tree = lxml.etree.parse(StringIO.StringIO(lxml.etree.tostring(xml)), parser)
    print lxml.etree.tostring(tree, pretty_print = True)

