from collections import Counter

from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def __init__(self):
        super().__init__()
        self.asgi_app.registration_call_counter = Counter()  # type: ignore
        self.asgi_app.deregistration_call_counter = Counter()  # type: ignore
