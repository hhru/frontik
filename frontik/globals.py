import time


class Stats(object):
    def __init__(self):
        self.page_count = 0
        self.http_reqs_count = 0
        self.http_reqs_size_sum = 0
        self.start_time = time.time()

    def next_request_id(self):
        self.page_count += 1
        return self.page_count

global_stats = Stats()
