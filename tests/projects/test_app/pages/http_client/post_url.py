import re

import frontik.handler
from frontik.util import any_to_bytes, any_to_unicode
from typing import Any
from frontik.handler import router
FIELDS: dict[str, Any] = {
    'fielda': 'hello',
    'fieldb': '',
    'field3': 'None',
    'field4': '0',
    'field5': 0,
    'field6': False,
    'field7': ['1', '3', 'jiji', bytes([1, 2, 3])]
}

FILES: dict[str, list] = {
    'field9': [{'filename': 'file0', 'body': b'\x10\x20\x30'}],
    'field10': [
        {'filename': 'file1', 'body': b'\x01\x02\x03'},
        {'filename': 'файл 01-12_25.abc', 'body': 'Ёконтент 123 !"№;%:?*()_+={}[]'}
    ]
}


class Page(frontik.handler.PageHandler):
    @router.get()
    async def get_page(self):
        result = await self.post_url(self.request.host, self.request.path, data=FIELDS, files=FILES)
        if not result.failed:
            self.json.put(result.data)

    @router.post()
    async def post_page(self):
        errors_count = 0
        body_parts = self.request.body.split(b'\r\n--')

        for part in body_parts:
            field_part = re.search(rb'name="(?P<name>.+)"\r\n\r\n(?P<value>.*)', part)
            file_part = re.search(rb'name="(?P<name>.+)"; filename="(?P<filename>.+)"\r\n'
                                  rb'Content-Type: \S+\r\n\r\n(?P<value>.*)', part)

            if field_part:
                val = field_part.group('value')
                name = any_to_unicode(field_part.group('name'))

                if isinstance(FIELDS[name], list) and all(val != any_to_bytes(x) for x in FIELDS[name]):
                    errors_count += 1
                elif not isinstance(FIELDS[name], list) and any_to_bytes(FIELDS[name]) != val:
                    errors_count += 1

            elif file_part:
                val = file_part.group('value')
                name = any_to_unicode(file_part.group('name'))
                filename = file_part.group('filename')

                for file in FILES[name]:
                    if any_to_bytes(file['filename']) == filename and any_to_bytes(file['body']) != val:
                        errors_count += 1

            elif re.search(b'name=', part):
                errors_count += 1

        self.json.put({'errors_count': errors_count})
