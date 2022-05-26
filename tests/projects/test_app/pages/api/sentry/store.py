import frontik.handler


class Page(frontik.handler.AwaitablePageHandler):
    exceptions = []

    async def post_page(self):
        Page.exceptions.append(
            self.get_sentry_logger().sentry_client.decode(self.request.body)
        )

    async def get_page(self):
        self.json.put({
            'exceptions': Page.exceptions
        })

    async def delete_page(self):
        Page.exceptions = []
