# _*_ coding: utf-8 _*_

import unittest

from lxml import etree

from frontik.testing import test_utils


class TestHelpers(unittest.TestCase):

    def test_remove_xpath(self):
        root = etree.fromstring('''
            <root>
                <removeMe ppp="mmm"/>
                <level2>
                    <removeMe2 n="1"/>
                    <removeMe2 n="2"/>
                </level2>
            </root>
            '''.strip())
        xpath1 = 'removeMe[@ppp="mmm"]'
        xpath2 = 'level2/removeMe2'

        self.assertTrue(len(root.xpath(xpath1)) == 1)
        self.assertTrue(len(root.xpath(xpath2)) == 2)

        test_utils.remove_xpaths(root, [xpath1, xpath2])

        self.assertTrue(len(root.xpath(xpath1)) == 0)
        self.assertTrue(len(root.xpath(xpath2)) == 0)


class TestXmlResponseMixin(unittest.TestCase, test_utils.XmlResponseTestCaseMixin):

    # ----------------------------------------------------
    # assertXmlAlmostEquals
    def test_assertXmlAlmostEquals_abs_equals(self):
        tree1_str, _, = self._get_almost_equals_xml()
        tree1 = etree.fromstring(tree1_str)
        tree1_2 = etree.fromstring(tree1_str)
        try:
            self.assertXmlAlmostEquals(tree1_str, tree1_str)
            self.assertXmlAlmostEquals(tree1, tree1_2)
        except self.failureException, e:
            self.fail('XML should be absolute equals (Reported error: "{0!s}")'.format(e))

    def test_assertVacancyXmlAlmostEquals_with_strings(self):
        tree1_str, tree2_str = self._get_almost_equals_xml()
        try:
            self.assertXmlAlmostEquals(tree1_str, tree2_str)
        except self.failureException, e:
            self.fail('XML should be almost equals (Reported error: "{0!s}")'.format(e))

    def test_assertXmlAlmostEquals_with_tree(self):
        tree1_str, tree2_str = self._get_almost_equals_xml()
        tree1 = etree.fromstring(tree1_str)
        tree2 = etree.fromstring(tree2_str)
        try:
            self.assertXmlAlmostEquals(tree1, tree2)
        except self.failureException, e:
            self.fail('XML should be almost equals (Reported error: "{0!s}")'.format(e))

    def test_assertXmlAlmostEquals_same_tags_order(self):
        x1_str = '''
            <elem>
                <a/>
                <a>
                    <c prop="1">
                        <d prop="x"/>
                        <d prop="y"/>
                        <d/>
                    </c>
                    <c prop="1" a="1"/>
                    <c/>
                </a>
            </elem>
            '''.strip()

        x2_str = '''
            <elem>
                <a>
                    <c/>
                    <c prop="1" a="1"/>
                    <c prop="1">
                        <d prop="x"/>
                        <d/>
                        <d prop="y"/>
                    </c>
                </a>
                <a/>
            </elem>
            '''.strip()
        try:
            self.assertXmlAlmostEquals(x1_str, x2_str)
        except self.failureException, e:
            self.fail('XML should be almost equals (Reported error: "{0!s}")'.format(e))

    # ----------------------------------------------------
    # assertXmlCompatible
    def test_assertXmlCompatible_abs_equals(self):
        tree1_str, _ = self._get_almost_equals_xml()
        try:
            self.assertXmlCompatible(tree1_str, tree1_str)
        except self.failureException, e:
            self.fail('XML should be absolute equals (Reported error: "{0!s}")'.format(e))

    def test_assertXmlCompatible_with_extra_property(self):
        old = '''
            <elem>
                <a answer="42" douglas="adams"/>
            </elem>
            '''.strip()

        # add: elem[@prop], a[@new], a[@new2]
        new = '''
            <elem prop="some">
                <a answer="42" new2="no" douglas="adams" new="yes"/>
            </elem>
            '''.strip()
        try:
            self.assertXmlCompatible(old, new)
        except self.failureException, e:
            self.fail('XML should be compatible (Reported error: "{0!s}")'.format(e))

    def test_assertXmlCompatible_with_extra_tags(self):
        old = '''
            <elem>
                <z prop="1"/>
                <a>
                    <c/>
                    <c month="jan"/>
                    <b/>
                </a>
                <z prop="3"/>
                <a disabled="true"/>
                <txt>some text</txt>
            </elem>
            '''.strip()

        # add extra tags: yy, dd, txt, aa, new
        # reoder: elem/*, elem/a/*
        new = '''
            <elem>
                <a disabled="true"/>
                <a>
                    <aa/>
                    <b/>
                    <c month="apr"/>
                    <c month="jan"/>
                    <c/>
                    <dd/>
                </a>
                <txt>some text</txt>
                <txt>some new text</txt>
                <z prop="3"/>
                <z prop="1">
                    <new nested="tag"/>
                </z>
                <yy/>
            </elem>
            '''.strip()
        try:
            self.assertXmlCompatible(old, new)
        except self.failureException, e:
            self.fail('XML should be compatible (Reported error: "{0!s}")'.format(e))

    def test_assertXmlCompatible_incompatible_property(self):
        old = '''
            <elem>
                <a answer="42" douglas="adams"/>
            </elem>
            '''.strip()

        # remove: a[@answer], add a[@extra]
        new = '''
            <elem>
                <a douglas="adams" extra="extra"/>
            </elem>
            '''.strip()
        self.assertRaises(self.failureException, self.assertXmlCompatible, old, new)

    def test_assertXmlCompatible_incompatible_less_tags(self):
        old = '''
            <elem>
                <a>
                    <b/>
                    <c/>
                </a>
                <m/>
                <z/>
            </elem>
            '''.strip()

        # remove: z
        # reorder: m<->a
        new = '''
            <elem>
                <m/>
                <a>
                    <b/>
                    <c/>
                </a>
            </elem>
            '''.strip()
        try:
            self.assertXmlCompatible(old, new)
        except self.failureException, e:
            self.assertTrue('Children length differs' in str(e))

    # ----------------------------------------------------
    # helpers
    def _get_almost_equals_xml(self):
        tree1_str = '''
            <elem start="17" end="18">
                <zAtrib/>
                <aAtrib>
                    <cAtrib/>
                    <bAtrib a="1" b="2"/>
                </aAtrib>
            </elem>
            '''.strip()
        #props and tags order changed
        tree2_str = '''
            <elem end="18" start="17" >
                <aAtrib>
                    <bAtrib b="2" a="1"/>
                    <cAtrib/>
                </aAtrib>
                <zAtrib/>
            </elem>
            '''.strip()
        return tree1_str, tree2_str
