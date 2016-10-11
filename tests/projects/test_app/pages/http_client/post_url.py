# coding=utf-8

import re

import frontik.handler
from frontik.util import any_to_bytes, any_to_unicode

FIELDS = {
    'fielda': 'hello',
    'fieldb': '',
    'field3': 'None',
    'field4': '0',
    'field5': 0,
    'field6': False,
    'field7': ['1', '3', 'jiji', bytes([1, 2, 3])]
}

FILES = {
    'field9': [{'filename': 'file0', 'body': b'\x10\x20\x30'}],
    'field10': [
        {'filename': 'file1', 'body': b'\x01\x02\x03'},
        {'filename': u'файл 01-12_25.abc', 'body': u'Ёконтент 123 !"№;%:?*()_+={}[]'}
    ]
}


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def callback_post(element, response):
            self.doc.put(element.text)

        self_uri = self.request.host + self.request.path
        self.post_url(self_uri, data=FIELDS, files=FILES, callback=callback_post)

    def post_page(self):
        body_parts = self.request.body.split(b'\r\n--')

        for part in body_parts:
            field_part = re.search(b'name="(?P<name>.+)"\r\n\r\n(?P<value>.*)', part)
            file_part = re.search(b'name="(?P<name>.+)"; filename="(?P<filename>.+)"\r\n'
                                  b'Content-Type: application/octet-stream\r\n\r\n(?P<value>.*)', part)

            if field_part:
                val = field_part.group('value')
                name = any_to_unicode(field_part.group('name'))

                if isinstance(FIELDS[name], list) and all(val != any_to_bytes(x) for x in FIELDS[name]):
                    self.doc.put('BAD')
                elif not isinstance(FIELDS[name], list) and any_to_bytes(FIELDS[name]) != val:
                    self.doc.put('BAD')

            elif file_part:
                val = file_part.group('value')
                name = any_to_unicode(file_part.group('name'))
                filename = file_part.group('filename')

                for file in FILES[name]:
                    if any_to_bytes(file['filename']) == filename and any_to_bytes(file['body']) != val:
                        self.doc.put('BAD')

            elif re.search(b'name=', part):
                self.doc.put('BAD')
