# coding=utf-8

import unittest

from lxml import etree

from frontik.testing import xml_asserts


class TestXmlResponseMixin(unittest.TestCase, xml_asserts.XmlTestCaseMixin):

    TREE1 = '''
        <elem start="17" end="18">
            <zAtrib/>
            <aAtrib>
                <cAtrib/>
                <bAtrib a="1" b="2"/>
            </aAtrib>
        </elem>
        '''.strip()

    TREE2 = '''
        <elem end="18" start="17" >
            <aAtrib>
                <bAtrib b="2" a="1"/>
                <cAtrib/>
            </aAtrib>
            <zAtrib/>
        </elem>
        '''.strip()

    def test_assertXmlEqual_abs_equals(self):
        try:
            self.assertXmlEqual(self.TREE1, self.TREE1)
            self.assertXmlEqual(etree.fromstring(self.TREE1), etree.fromstring(self.TREE1))
        except self.failureException as e:
            self.fail('XML should be absolute equals (Reported error: "{0!s}")'.format(e))

    def test_assertXmlEqual_with_strings(self):
        try:
            self.assertXmlEqual(self.TREE1, self.TREE2)
        except self.failureException as e:
            self.fail('XML should be almost equals (Reported error: "{0!s}")'.format(e))

    def test_assertXmlEqual_with_tree(self):
        try:
            self.assertXmlEqual(etree.fromstring(self.TREE1), etree.fromstring(self.TREE2))
        except self.failureException as e:
            self.fail('XML should be almost equals (Reported error: "{0!s}")'.format(e))

    def test_assertXmlEqual_same_tags_order(self):
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
            self.assertXmlEqual(x1_str, x2_str)
        except self.failureException as e:
            self.fail('XML should be almost equals (Reported error: "{0!s}")'.format(e))

    def test_assertXmlCompatible_abs_equals(self):
        try:
            self.assertXmlCompatible(self.TREE1, self.TREE1)
        except self.failureException as e:
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
        except self.failureException as e:
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
        except self.failureException as e:
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
        except self.failureException as e:
            self.assertIn('Children length differs', str(e))
