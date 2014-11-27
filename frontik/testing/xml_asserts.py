# coding=utf-8

import itertools

from lxml import etree


def _describe_element(elem):
    root = elem.getroottree()
    if not root:
        return '? [tag name: {}]'.format(elem.tag)
    else:
        return root.getpath(elem)


def _xml_text_compare(t1, t2):
    return (t1 or '').strip() == (t2 or '').strip()


def _xml_tags_compare(a, b):
    # (1): compare tag names
    res = cmp(a.tag, b.tag)
    if res != 0:
        return res

    # (2): compare attributes
    res = cmp(dict(a.attrib), dict(b.attrib))
    if res != 0:
        return res

    # (3): compare children
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

    for attrib, value in xml1.attrib.iteritems():
        if xml2.attrib.get(attrib) != value:
            reporter('Attributes do not match: {attr}={v1!r}, {attr}={v2!r} (path: {path})'
                     .format(attr=attrib, v1=value, v2=xml2.attrib.get(attrib), path=_describe_element(xml1)))
            return False

    if compare_xml2_attribs:
        for attrib in xml2.attrib:
            if attrib not in xml1.attrib:
                reporter('xml2 has an attribute xml1 is missing: {attrib} (path: {path})'
                         .format(attrib=attrib, path=_describe_element(xml2)))
                return False

    if not _xml_text_compare(xml1.text, xml2.text):
        reporter('Text: {t1} != {t2} (path: {path})'
                 .format(t1=xml1.text.encode('utf-8'), t2=xml2.text.encode('utf-8'), path=_describe_element(xml1)))
        return False

    if not _xml_text_compare(xml1.tail, xml2.tail):
        reporter('Tail: {tail1} != {tail2}'.format(
            tail1=xml1.tail.encode('utf-8'), tail2=xml2.tail.encode('utf-8'), path=_describe_element(xml1)))
        return False

    return True


class _DownstreamReporter(object):

    def __init__(self):
        self.last_error = None

    def __call__(self, *args, **kwargs):
        self.last_error = args[0]


def _xml_compare(xml1, xml2, check_tags_order=False, reporter=lambda x: None):
    """Compare two etree.Element objects.

    Based on https://bitbucket.org/ianb/formencode/src/tip/formencode/doctest_xml_compare.py#cl-70
    """
    if not _xml_compare_tag_attribs_text(xml1, xml2, reporter=reporter):
        return False

    children1 = xml1.getchildren()
    children2 = xml2.getchildren()
    if len(children1) != len(children2):
        reporter('Children length differs, {len1} != {len2} (path: {path})'
                 .format(len1=len(children1), len2=len(children2), path=_describe_element(xml1)))
        return False

    if not check_tags_order:
        children1.sort(_xml_tags_compare)
        children2.sort(_xml_tags_compare)

    i = 0
    for c1, c2 in zip(children1, children2):
        i += 1
        if not _xml_compare(c1, c2, check_tags_order, reporter):
            reporter('Children not matched (path: {path})'
                     .format(n=i, tag1=c1.tag, tag2=c2.tag, path=_describe_element(xml1)))
            return False

    return True


def _xml_check_compatibility(old_xml, new_xml, reporter=lambda x: None):
    """Check compatibility of two xml documents (new_xml is an extension of old_xml).

    new_xml >= old_xml:
        * new_xml should contains all attribs and properties from old_xml
        * new_xml may have any extra attribs
        * new_xml may have any extra properties
    """
    pre_cmp = _xml_compare_tag_attribs_text(old_xml, new_xml, reporter=reporter, compare_xml2_attribs=False)
    if not pre_cmp:
        return False

    old_children = old_xml.getchildren()
    new_children = new_xml.getchildren()

    if len(old_children) == 0:
        return True

    elif len(new_children) < len(old_children):
        reporter('Children length differs, {len1} < {len2} (path: {path})'
                 .format(len1=len(old_children), len2=len(new_children), path=_describe_element(old_xml)))
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
                         .format(tag=tag, path=_describe_element(old_xml)))
                return False

            any_matched = False
            downstream_reporter = _DownstreamReporter()
            for match_child in new_children_index[tag]:
                is_compatible = _xml_check_compatibility(child, match_child, downstream_reporter)
                if is_compatible:
                    any_matched = True
                    new_children_index[tag].remove(match_child)
                    break
            if not any_matched:
                reporter(downstream_reporter.last_error)
                return False
        return True


class XmlTestCaseMixin(object):
    """Mixin for L{unittest.TestCase}."""

    def _assert_xml_compare(self, cmp_func, xml1, xml2, msg, **kwargs):
        if msg is None:
            msg = 'XML documents are not equal'
        if not isinstance(xml1, etree._Element):
            xml1 = etree.fromstring(xml1)
        if not isinstance(xml2, etree._Element):
            xml2 = etree.fromstring(xml2)

        def _fail_reporter(err_message):
            self.fail('{0}: {1}'.format(msg, err_message))

        cmp_func(xml1, xml2, reporter=_fail_reporter, **kwargs)

    def assertXmlEqual(self, expected, real, msg=None, check_tags_order=False):
        """Assert that two xml documents are equal (the order of elements and attributes is ignored)."""
        self._assert_xml_compare(_xml_compare, expected, real, msg, check_tags_order=check_tags_order)

    def assertXmlCompatible(self, old, new, msg=None):
        """Assert that one xml document is an extension of another."""
        self._assert_xml_compare(_xml_check_compatibility, old, new, msg)
