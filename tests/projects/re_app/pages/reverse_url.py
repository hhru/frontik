from frontik.handler import PageHandler


class Page(PageHandler):
    async def get_page(self):
        if self.get_argument('fail_args', 'false') != 'false':
            self.text = self.reverse_url('two_ids', 1)

        if self.get_argument('fail_missing', 'false') != 'false':
            self.text = self.reverse_url('missing', 1)

        self.json.put({
            'args': self.reverse_url('two_ids', 1, 2),
            'args_and_kwargs': self.reverse_url('two_ids', 2, id1=1),
            'kwargs': self.reverse_url('two_ids', id1=1, id2=2),
        })
