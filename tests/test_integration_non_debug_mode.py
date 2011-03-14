# -*- coding: utf-8 -*-

from __future__ import with_statement

import nose
import urllib2

from integration_util import FrontikTestInstance

frontik_prod = FrontikTestInstance("./tests/projects/frontik_non_debug_mode.cfg")


def simple2_test():
    with frontik_prod.get_page_text('test_app/simple') as html:
        assert(not html.find('ok') is None)

def test_basic_auth_fail():
    with frontik_prod.instance() as srv_port:
        try:
            res = urllib2.urlopen('http://localhost:{0}/test_app/basic_auth/'.format(srv_port)).info()
            assert(res.getcode() != 200)
        except urllib2.HTTPError, e:
            assert(e.code == 401)


def test_basic_auth_fail_on_wrong_pass():
    with frontik_prod.instance() as srv_port:
        page_url = 'http://localhost:{0}/test_app/basic_auth/'.format(srv_port)
        
        # Create an OpenerDirector with support for Basic HTTP Authentication...
        auth_handler = urllib2.HTTPBasicAuthHandler()
        auth_handler.add_password(realm='Secure Area',
                                  uri=page_url,
                                  user='user',
                                  passwd='bad')
        opener = urllib2.build_opener(auth_handler)
        try: 
            res = opener.open(page_url)
            assert(res.getcode() == 401)
        except urllib2.HTTPError, e:
            assert(e.code == 401)


def test_basic_auth_pass():
    with frontik_prod.instance() as srv_port:
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
    

if __name__ == '__main__':
    nose.main()
