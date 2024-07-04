from collections import Counter

from frontik.app import FrontikApplication


class TestApplication(FrontikApplication):
    def __init__(self):
        super().__init__()
        self.registration_call_counter: Counter = Counter()
        self.deregistration_call_counter: Counter = Counter()
