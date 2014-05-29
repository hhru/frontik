# coding=utf-8

import base64
import urllib2

from tests import frontik_non_debug


def test_simple():
    with frontik_non_debug.get_page_text('test_app/simple') as html:
        assert(not html.find('ok') is None)


def test_basic_auth_fail():
    with frontik_non_debug.instance() as srv_port:
        try:
            res = urllib2.urlopen('http://localhost:{0}/test_app/basic_auth/'.format(srv_port)).info()
            assert(res.getcode() == 401)
        except urllib2.HTTPError, e:
            assert(e.code == 401)


def test_basic_auth_fail_on_wrong_pass():
    with frontik_non_debug.instance() as srv_port:
        page_url = 'http://localhost:{0}/test_app/basic_auth/'.format(srv_port)

        req = urllib2.Request(page_url)
        req.add_header('Authorization', 'Basic {0}'.format(base64.encodestring('user:bad')))
        try: 
            res = urllib2.urlopen(req)
            assert(res.getcode() == 401)
        except urllib2.HTTPError, e:
            assert(e.code == 401)


def test_basic_auth_pass():
    with frontik_non_debug.instance() as srv_port:
        page_url = 'http://localhost:{0}/test_app/basic_auth/'.format(srv_port)
        
        # Create an OpenerDirector with support for Basic HTTP Authentication...
        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password(realm='Secure Area',
                                  uri=page_url,
                                  user='user',
                                  passwd='god')
        opener = urllib2.build_opener(auth_handler)
        res = opener.open(page_url)

        assert(res.getcode() == 200)
