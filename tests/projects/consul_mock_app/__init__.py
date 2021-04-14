from collections import Counter

from frontik.app import FrontikApplication
from tests.projects.consul_mock_app.pages import deregister
from tests.projects.consul_mock_app.pages.v1.kv.host.hostname.weight import weight
from tests.projects.consul_mock_app.pages.v1.kv.upstream import upstream


class TestApplication(FrontikApplication):

    def __init__(self, **settings):
        super().__init__(**settings)
        self.registration_call_counter = Counter()
        self.deregistration_call_counter = Counter()

    def application_urls(self):
        return [(r'^/v1/agent/service/deregister/(?P<serviceId>[a-zA-Z\-_0-9\.:]+)$', deregister.Page),
                (r'^/v1/kv/host/([a-zA-Z\-_0-9\.:\-]+)/weight', weight.Page),
                (r'^/v1/kv/upstream', upstream.Page),
                *super().application_urls(), ]
