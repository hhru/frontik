from collections import Counter

from frontik.app import FrontikApplication
from tests.projects.consul_mock_app.pages import deregister


class TestApplication(FrontikApplication):

    def __init__(self, **settings):
        super().__init__(**settings)
        self.registration_call_counter = Counter()
        self.deregistration_call_counter = Counter()

    def application_urls(self):
        return [(r'^/v1/agent/service/deregister/(?P<serviceId>[a-zA-Z\-_0-9\.:]+)$', deregister.Page),
                *super().application_urls(), ]
