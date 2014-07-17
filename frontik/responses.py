# coding=utf-8

from collections import namedtuple
from functools import partial
import re

import lxml.etree as etree
import simplejson as json

import frontik.frontik_logging as frontik_logging


class FailedRequestException(Exception):
    def __init__(self, **kwargs):
        self.attrs = kwargs


class RequestResult(object):
    __slots__ = ('data', 'response', 'exception')

    ResponseData = namedtuple('ResponseData', ('data', 'response'))

    def __init__(self):
        self.data = None
        self.response = None
        self.exception = None

    def set(self, data, response):
        self.data = data
        self.response = response

    def get(self):
        return RequestResult.ResponseData(self.data, self.response)

    def set_exception(self, exception):
        self.exception = exception


def _parse_response(response, logger=frontik_logging.log, parser=None, response_type=None):
    try:
        return parser(response.body)
    except:
        _preview_len = 100

        if len(response.body) > _preview_len:
            body_preview = '{0}...'.format(response.body[:_preview_len])
        else:
            body_preview = response.body

        logger.exception('failed to parse {0} response from {1}, bad data: "{2}"'.format(
            response_type, response.effective_url, body_preview))

        raise FailedRequestException(url=response.effective_url, reason='invalid {0}'.format(response_type))


_xml_parser = etree.XMLParser(strip_cdata=False)
_parse_response_xml = partial(_parse_response,
                              parser=lambda x: etree.fromstring(x, parser=_xml_parser),
                              response_type='XML')

_parse_response_json = partial(_parse_response,
                               parser=json.loads,
                               response_type='JSON')

DEFAULT_REQUEST_TYPES = {
    re.compile('.*xml.?'): _parse_response_xml,
    re.compile('.*json.?'): _parse_response_json,
    re.compile('.*text/plain.?'): (lambda response, logger: response.body),
}
