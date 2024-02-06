from __future__ import annotations

import json
from typing import TYPE_CHECKING

from frontik.handler import PageHandler, router

if TYPE_CHECKING:
    from tests.projects.consul_mock_app import TestApplication


class Page(PageHandler):
    @router.get()
    async def get_page(self):
        self.set_status(200)
        self.application: TestApplication
        self.text = json.dumps(self.application.registration_call_counter)
