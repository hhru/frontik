# coding=utf-8

import urllib2

import nose

from integration_util import FrontikTestInstance

frontik_debug = FrontikTestInstance('./tests/projects/frontik.cfg')
POSTPROCESS_URL = 'http://localhost:{0}/test_app/postprocess/?{1}'


def test_no_postprocessors():
    with frontik_debug.instance() as srv_port:
        try:
            response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, ''))
            assert response.code == 200
            assert response.read() == '<html>\n<h1>{{header}}</h1>{{content}}\n</html>\n'
        except Exception:
            assert False


def test_early_postprocessors():
    with frontik_debug.instance() as srv_port:
        try:
            urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'fail_early'))
            assert False
        except Exception as e:
            assert e.code == 400


def test_template_postprocessors_single():
    with frontik_debug.instance() as srv_port:
        try:
            response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'header'))
            assert response.code == 200
            assert response.read() == '<html>\n<h1>HEADER</h1>{{content}}\n</html>\n'
        except Exception:
            assert False


def test_template_postprocessors_multiple():
    with frontik_debug.instance() as srv_port:
        try:
            response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'header&content'))
            assert response.code == 200
            assert response.read() == '<html>\n<h1>HEADER</h1>CONTENT\n</html>\n'
        except Exception:
            assert False


def test_late_postprocessors():
    with frontik_debug.instance() as srv_port:
        try:
            response = urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'nocache&addserver'))
            assert response.code == 200
            assert response.headers['cache-control'] == 'no-cache'
            assert response.headers['server'] == 'Frontik'
        except Exception:
            assert False


def test_late_postprocessors_after_error():
    with frontik_debug.instance() as srv_port:
        try:
            urllib2.urlopen(POSTPROCESS_URL.format(srv_port, 'fail_early&nocache&addserver'))
            assert False
        except Exception as e:
            assert e.code == 400
            assert e.headers['cache-control'] == 'no-cache'
            assert e.headers['server'] == 'Frontik'

if __name__ == '__main__':
    nose.main()
