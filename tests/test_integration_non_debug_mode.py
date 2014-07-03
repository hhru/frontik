# coding=utf-8

import base64

from .instances import frontik_non_debug


def test_simple():
    html = frontik_non_debug.get_page_text('test_app/simple')
    assert html.find('ok') is not None


def test_basic_auth_fail():
    response = frontik_non_debug.get_page('test_app/basic_auth')
    assert(response.status_code == 401)


def test_basic_auth_fail_on_wrong_pass():
    response = frontik_non_debug.get_page(
        'test_app/basic_auth', headers={'Authorization': 'Basic {}'.format(base64.encodestring('user:bad'))})
    assert(response.status_code == 401)


def test_basic_auth_pass():
    response = frontik_non_debug.get_page('test_app/basic_auth', auth=('basic', 'user', 'god'))
    assert(response.status_code == 200)
