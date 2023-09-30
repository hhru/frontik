from __future__ import annotations

from typing import TYPE_CHECKING

from frontik.handler import PageHandler

if TYPE_CHECKING:
    from tests.projects.consul_mock_app import TestApplication


class Page(PageHandler):
    def __init__(self, *args, **kwargs):
        self.application: TestApplication
        super().__init__(*args, **kwargs)

    async def get_page(self):
        self.set_status(200)
        self.application.registration_call_counter['get_page'] += 1

    async def put_page(self):
        self.set_status(200)
        self.application.registration_call_counter['put_page'] += 1

    async def post_page(self):
        self.set_status(200)
        self.application.registration_call_counter['post_page'] += 1
