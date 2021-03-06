import frontik.handler


class Page(frontik.handler.PageHandler):
    exceptions = []

    def post_page(self):
        Page.exceptions.append(
            self.get_sentry_logger().sentry_client.decode(self.request.body)
        )

    def get_page(self):
        self.json.put({
            'exceptions': Page.exceptions
        })

    def delete_page(self):
        Page.exceptions = []
