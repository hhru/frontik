from typing import Any

import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        fail_callback = self.get_argument('fail_callback', 'false') == 'true'
        fail_request = self.get_argument('fail_request', 'false') == 'true'

        async def task() -> Any:
            request_result = await self.post_url(self.request.host, self.request.path + '?data=2')
            if fail_callback:
                msg = "I'm dying!"
                raise Exception(msg)
            return request_result.data

        self.json.put(
            self.group(
                {
                    '1': self.post_url(self.request.host, self.request.path + '?data=1'),
                    '2': task(),
                    '3': self.post_url(
                        self.request.host,
                        self.request.path,
                        data={'data': '3' if not fail_request else None},
                        parse_on_error=False,
                    ),
                },
            ),
        )

        result = await self.group({'4': self.post_url(self.request.host, self.request.path + '?data=4')})

        self.json.put({'future_callback_result': result['4'].data['4']})
        self.json.put({'final_callback_called': True})

    async def post_page(self):
        self.json.put({self.get_argument('data'): 'yay'})
