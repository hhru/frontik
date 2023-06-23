import frontik.handler


class Page(frontik.handler.PageHandler):
    async def get_page(self):
        state = {
            'second_callback_must_be_async': True,
        }

        def second_additional_callback(task):
            state['second_callback_must_be_async'] = False

        def additional_callback(task):
            assert task is request_task

            self.json.put({
                'additional_callback_called': True
            })

            task.add_done_callback(second_additional_callback)
            assert state['second_callback_must_be_async']

        request_task = self.run_task(self.post_url(self.request.host, self.request.path))
        request_task.add_done_callback(additional_callback)

    async def post_page(self):
        self.json.put({
            'yay': 'yay'
        })
