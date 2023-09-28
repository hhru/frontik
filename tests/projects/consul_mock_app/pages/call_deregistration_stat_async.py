from __future__ import annotations
from typing import TYPE_CHECKING
import json

from frontik.handler import PageHandler
if TYPE_CHECKING:
    from tests.projects.consul_mock_app import TestApplication

class Page(PageHandler):
    async def get_page(self):
        self.set_status(200)
        self.application: TestApplication
        self.text = json.dumps(self.application.deregistration_call_counter)
