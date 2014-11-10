# coding=utf-8

import time

from lxml import etree

import frontik.util

parser = etree.XMLParser()


def xml_from_file(filename, log):
    def _source_comment(src):
        return etree.Comment('Source: {0}'.format(frontik.util.asciify_url(src).replace('--', '%2D%2D')))

    try:
        res = etree.parse(filename).getroot()
        return [_source_comment(filename), res]
    except IOError:
        log.error('failed to read xml file: %s', filename)
        raise
    except:
        log.error('failed to parse xml file %s', filename)
        raise


def xsl_from_file(filename, log):
    start_time = time.time()
    result = etree.XSLT(etree.parse(filename, parser))
    log.info('read xsl file %s in %.2fms', filename, (time.time() - start_time) * 1000)
    return result


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
