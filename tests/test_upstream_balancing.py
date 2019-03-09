import random
import unittest

# noinspection PyUnresolvedReferences
import frontik.options

from frontik.http_client import Upstream, Server


def run_simulation(upstream, requests_interval, requests, max_execution_time):
    timeline = []
    mapping = {}
    done = [0] * len(upstream.servers)

    for i in range(requests_interval + max_execution_time + 1):
        timeline.append([])

    for i in range(requests):
        start_time = random.randint(0, requests_interval)
        timeline[start_time].append((i, True))
        request_time = random.randint(1, max_execution_time)
        timeline[start_time + request_time].append((i, False))

    for commands in timeline:
        for (index, borrow) in commands:
            if borrow:
                fd, address, _, _ = upstream.borrow_server()
                done[fd] = done[fd] + 1
                mapping[index] = fd
            else:
                upstream.return_server(mapping[index], False)
                del mapping[index]

    return done


def _upstream(weights):
    return Upstream('upstream', {}, [Server(str(weight), weight) for weight in weights])


class TestHttpError(unittest.TestCase):
    def check_distribution(self, requests, weights):
        if len(requests) != len(weights) or len(requests) <= 1:
            raise ValueError(f'invalid input data: {requests}, {weights}')

        for i in range(1, len(requests)):
            request_ratio = float(requests[i]) / float(requests[i - 1])
            weights_ratio = float(weights[i]) / float(weights[i - 1])

            self.assertTrue(
                abs(request_ratio - weights_ratio) <= 0.3,
                f'{requests} and {weights} ratio difference for elements {i - 1} and {i} is too big: '
                f'{request_ratio} vs {weights_ratio}'
            )

    def test_sparse_requests(self):
        weights = [50, 100, 200]
        requests = run_simulation(_upstream(weights), requests_interval=10000, requests=3500, max_execution_time=200)

        self.check_distribution(requests, weights)

    def test_dense_requests(self):
        weights = [50, 100, 200]
        requests = run_simulation(_upstream(weights), requests_interval=10000, requests=100000, max_execution_time=1000)

        self.check_distribution(requests, weights)

    def test_short_execution_time(self):
        weights = [50, 100, 200]
        requests = run_simulation(_upstream(weights), requests_interval=800, requests=3500, max_execution_time=10)

        self.check_distribution(requests, weights)

    def test_long_execution_time(self):
        weights = [50, 100, 200]
        requests = run_simulation(_upstream(weights), requests_interval=10000, requests=3500, max_execution_time=10000)

        self.check_distribution(requests, weights)
