# coding=utf-8

import os.path

from lxml import etree

import frontik.util

parser = etree.XMLParser()


def xml_from_file(filename, log):
    def _source_comment(src):
        return etree.Comment('Source: {0}'.format(frontik.util.asciify_url(src).replace('--', '%2D%2D')))

    if os.path.exists(filename):
        try:
            res = etree.parse(filename).getroot()
            return [_source_comment(filename), res]
        except:
            log.exception('failed to parse xml file %s', filename)
            raise
    else:
        log.error('file not found: %s', filename)
        raise Exception('tried to load non-existent xml file')


def xsl_from_file(filename, log):
    log.debug('read file %s', filename)
    return etree.XSLT(etree.parse(filename, parser))


def dict_to_xml(dict_value, element_name):
    element = etree.Element(element_name)
    if not isinstance(dict_value, dict):
        element.text = str(dict_value).decode('utf-8')
        return element

    for k, v in dict_value.items():
        element.append(dict_to_xml(v, k))
    return element


def xml_to_dict(xml):
    if len(xml) == 0:
        return xml.text.encode('ascii', 'xmlcharrefreplace') if xml.text is not None else ''

    dictionary = {}
    for e in xml:
        dictionary[e.tag] = xml_to_dict(e)
    return dictionary
