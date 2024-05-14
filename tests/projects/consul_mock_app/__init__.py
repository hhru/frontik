from collections import Counter

from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def __init__(self, **settings):
        super().__init__(**settings)
        self.registration_call_counter: Counter = Counter()
        self.deregistration_call_counter: Counter = Counter()
