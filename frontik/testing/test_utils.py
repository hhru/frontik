# -*- coding: utf-8 -*-

import StringIO
import itertools

import lxml
from lxml import etree


def pretty_print_xml(xml):
    parser = lxml.etree.XMLParser(remove_blank_text=True)
    tree = lxml.etree.parse(StringIO.StringIO(lxml.etree.tostring(xml)), parser)
    print lxml.etree.tostring(tree, pretty_print=True)


# ----------------------------------------------------
# XML comparing helpers


def _describe_element(elem):
    root = elem.getroottree()
    if not root:
        return '? [tag name: {0}]'.format(elem.tag)
    else:
        return root.getpath(elem)


def _xml_text_compare(t1, t2):
    return (t1 or '').strip() == (t2 or '').strip()


def _xml_tags_compare(a, b):
    # step 1 - cmp tag name
    res = cmp(a.tag, b.tag)
    if res != 0:
        return res

    # step 2 - cmp attribs
    res = cmp(dict(a.attrib), dict(b.attrib))
    if res != 0:
        return res

    # step 3 - cmp children
    a_children = a.getchildren()
    b_children = b.getchildren()
    a_children.sort(_xml_tags_compare)
    b_children.sort(_xml_tags_compare)
    for a_child, b_child in itertools.izip_longest(a_children, b_children):
        child_res = cmp(a_child, b_child)
        if child_res != 0:
            res = child_res
            break

    return res


def _xml_compare_tag_attribs_text(xml1, xml2, reporter, compare_xml2_attribs=True):
    if xml1.tag != xml2.tag:
        reporter('Tags do not match: {tag1} and {tag2} (path: {path})'
                 .format(tag1=xml1.tag, tag2=xml2.tag, path=_describe_element(xml1)))
        return False
    for attrib, value in xml1.attrib.items():
        if xml2.attrib.get(attrib) != value:
            reporter('Attributes do not match: {attr}={v1!r}, {attr}={v2!r} (path: {path})'
                     .format(attr=attrib, v1=value, v2=xml2.attrib.get(attrib), path=_describe_element(xml1)))
            return False
    if compare_xml2_attribs:
        for attrib in xml2.attrib.keys():
            if attrib not in xml1.attrib:
                reporter('xml2 has an attribute xml1 is missing: {attrib} (path: {path})'
                         .format(attrib=attrib, path=_describe_element(xml2)))
                return False
    if not _xml_text_compare(xml1.text, xml2.text):
        reporter('Text: {t1} != {t2} (path: {path})'
                 .format(t1=xml1.text.encode('utf-8'), t2=xml2.text.encode('utf-8'), path=_describe_element(xml1)))
        return False
    if not _xml_text_compare(xml1.tail, xml2.tail):
        reporter('Tail: {tail1} != {tail2}'
                 .format(tail1=xml1.tail.encode('utf-8'), tail2=xml2.tail.encode('utf-8'), path=_describe_element(xml1)))
        return False
    return True


class __DownstreamReporter(object):

    def __init__(self):
        self.last_error = None

    def __call__(self, *args, **kwargs):
        self.last_error = args[0]


def xml_compare(xml1, xml2, reorder_tags=True, reporter=None):
    """
    XML comparing for etree.Element
    Based on https://bitbucket.org/ianb/formencode/src/tip/formencode/doctest_xml_compare.py#cl-70
    """
    if reporter is None:
        reporter = lambda x: None
    pre_cmp = _xml_compare_tag_attribs_text(xml1, xml2, reporter=reporter)
    if not pre_cmp:
        return False
    children1 = xml1.getchildren()
    children2 = xml2.getchildren()
    if len(children1) != len(children2):
        reporter('Children length differs, {len1} != {len2} (path: {path})'
                 .format(len1=len(children1), len2=len(children2), path=_describe_element(xml1)))
        return False
    if reorder_tags:
        children1.sort(_xml_tags_compare)
        children2.sort(_xml_tags_compare)
    i = 0
    for c1, c2 in zip(children1, children2):
        i += 1
        if not xml_compare(c1, c2, reporter=reporter, reorder_tags=reorder_tags):
            reporter('Children not matched (path: {path})'
                     .format(n=i, tag1=c1.tag, tag2=c2.tag, path=_describe_element(xml1)))
            return False
    return True


def xml_check_compatibility(old, new, reorder_tags=True, reporter=None):
    """
    Check two xml compatibility.

    new_xml >= old_xml:
        * new_xml should contains all attribs and properties from old_xml
        * new_xml may have any extra attribs
        * new_xml may have any extra properties
    """
    if reporter is None:
        reporter = lambda x: None
    pre_cmp = _xml_compare_tag_attribs_text(old, new, reporter=reporter, compare_xml2_attribs=False)
    if not pre_cmp:
        return False

    old_children = old.getchildren()
    new_children = new.getchildren()
    if len(old_children) == 0:
        return True
    elif len(new_children) < len(old_children):
        reporter('Children length differs, {len1} < {len2} (path: {path})'
                 .format(len1=len(old_children), len2=len(new_children), path=_describe_element(old)))
        return False
    else:
        new_children_index = {}
        for child in new_children:
            tag = child.tag
            if tag not in new_children_index:
                new_children_index[tag] = []
            new_children_index[tag].append(child)
        for tag in new_children_index.iterkeys():
            new_children_index[tag].sort(_xml_tags_compare)

        old_children.sort(_xml_tags_compare)
        for child in old_children:
            tag = child.tag
            if tag not in new_children_index or len(new_children_index[tag]) == 0:
                reporter('Tag {tag} not exist in new xml (path: {path})'
                         .format(tag=tag, path=_describe_element(old)))
                return False

            any_matched = False
            downstream_reporter = __DownstreamReporter()
            for match_child in new_children_index[tag]:
                is_compatible = xml_check_compatibility(child, match_child, reorder_tags=reorder_tags,
                                                        reporter=downstream_reporter)
                if is_compatible:
                    any_matched = True
                    new_children_index[tag].remove(match_child)
                    break
            if not any_matched:
                reporter(downstream_reporter.last_error)
                return False
        return True


def remove_xpaths(elem, xpaths):
    """
    Remove element that matches xpath from it's parent.
    """
    for x in xpaths:
        res = elem.xpath(x)
        if len(res) == 0:
            continue
        for e in res:
            parent = e.getparent()
            if parent is not None:
                parent.remove(e)
    return elem


class XmlResponseTestCaseMixin(object):
    """
    Mixin for L{unittest.TestCase} or other class with similar API.

    Add assertion:
      * assertXmlAlmostEquals
      * assertXmlCompatible

    Add helpers:
      * remove_xpaths
    """

    # ----------------------------------------------------
    # Assertions
    def _xml_cmp_assertion(self, cmp_func, x1, x2, msg=None):
        if msg is None:
            msg = 'XML not equals'
        if not isinstance(x1, etree._Element):
            x1 = etree.fromstring(x1)
        if not isinstance(x2, etree._Element):
            x2 = etree.fromstring(x2)

        def _fail_reporter(err_message):
            self.fail('{0}: {1}'.format(msg, err_message))

        cmp_func(x1, x2, reorder_tags=True, reporter=_fail_reporter)

    def assertXmlAlmostEquals(self, expected, real, msg=None):
        """
        Assert that xml almost equals.
        Before comparing XML tags and properties will be ordered.
        If real or expected xml has some extra tags, assertion fails.
        """
        self._xml_cmp_assertion(xml_compare, expected, real, msg)

    def assertXmlCompatible(self, old, new, msg=None):
        """
        Assert that xml almost equals.
        Before comparing XML tags and properties will be ordered.
        If real or expected xml has some extra tags, assertion fails.
        """
        self._xml_cmp_assertion(xml_check_compatibility, old, new, msg)
