import logging
import time

from lxml import etree

from frontik.util import any_to_unicode

parser = etree.XMLParser()
xml_util_log = logging.getLogger('frontik.xml_util')


def xml_from_file(filename):
    try:
        return etree.parse(filename).getroot()
    except IOError:
        xml_util_log.error('failed to read xml file %s', filename)
        raise
    except Exception:
        xml_util_log.error('failed to parse xml file %s', filename)
        raise


def xsl_from_file(filename):
    start_time = time.time()
    result = etree.XSLT(etree.parse(filename, parser))
    xml_util_log.info('read xsl file %s in %.2fms', filename, (time.time() - start_time) * 1000)
    return result


def dict_to_xml(dict_value, element_name):
    element = etree.Element(element_name)
    if not isinstance(dict_value, dict):
        element.text = any_to_unicode(dict_value)
        return element

    for k, v in dict_value.items():
        element.append(dict_to_xml(v, k))
    return element


def xml_to_dict(xml):
    if len(xml) == 0:
        return xml.text if xml.text is not None else ''

    return {e.tag: xml_to_dict(e) for e in xml}
