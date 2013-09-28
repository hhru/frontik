import logging
import os.path
import urlparse

import lxml.etree as etree

log = logging.getLogger("frontik.xml_util")

parser = etree.XMLParser()


class PrefixResolver(etree.Resolver):
    def __init__(self, scheme, path):
        self.scheme = scheme
        self.path = os.path.abspath(path)

    def resolve(self, system_url, public_id, context):
        parsed_url = urlparse.urlsplit(system_url)
        if parsed_url.scheme == self.scheme:
            path = os.path.abspath(os.path.join(self.path, parsed_url.path))
            if not os.path.commonprefix([self.path, path]).startswith(self.path):
                raise etree.XSLTParseError('Open files out of XSL root is not allowed: {0}'.format(path))
            return self.resolve_filename(path, context)


def _abs_filename(base_filename, filename):
    if filename.startswith("/"):
        return filename
    else:
        base_dir = os.path.dirname(base_filename)
        return os.path.normpath(os.path.join(base_dir, filename))


def get_xsl_includes(filename, parser=parser):
    tree = etree.parse(filename, parser)
    namespaces = {'xsl': 'http://www.w3.org/1999/XSL/Transform'}
    return [_abs_filename(filename, i.get('href'))
            for i in tree.xpath('xsl:import|xsl:include', namespaces=namespaces)
            if i.get('href').find(':') == -1]


def read_xsl(filename, log=log, parser=parser):
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
