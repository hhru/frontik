import asyncio
import contextlib
import pickle
import time
from ctypes import c_bool, c_int
from multiprocessing import Lock, Queue, Value
from typing import Callable, Optional

from http_client import options as http_client_options
from http_client.balancing import Server, Upstream, UpstreamConfig

import frontik.process
from frontik.options import options
from frontik.process import WorkerState, fork_workers
from frontik.service_discovery import WorkerServiceDiscovery


async def worker_teardown(worker_exit_event):
    while True:
        await asyncio.sleep(0)
        try:
            worker_exit_event.get_nowait()
            asyncio.get_event_loop().stop()
        except:
            pass


def prepare_upstreams():
    options.upstreams = ['app']
    options.init_workers_timeout_sec = 2
    http_client_options.datacenters = ['Test']
    upstream_config = {
        Upstream.DEFAULT_PROFILE: UpstreamConfig(
            max_timeout_tries=10,
            retry_policy={'403': {'retry_non_idempotent': 'false'}, '500': {'retry_non_idempotent': 'true'}},
        ),
    }
    return {
        'upstream': Upstream(
            'upstream', upstream_config, [Server('12.2.3.5', 'dest_host'), Server('12.22.3.5', 'dest_host')]
        )
    }


def get_upstream_bytes(service_discovery):
    return pickle.dumps(list(service_discovery.get_upstreams_copy().values()))


def noop(*_args, **__kwargs):
    pass


class TestProcessFork:
    def setup_method(self):
        self._orig_supervise = frontik.process._supervise_workers
        self._orig_listener = frontik.process._worker_listener
        self._pipe_size_setter = frontik.process._set_pipe_size
        frontik.process._set_pipe_size = noop
        frontik.process._supervise_workers = noop

    def teardown_method(self):
        frontik.process._supervise_workers = self._orig_supervise
        frontik.process._worker_listener = self._orig_listener
        frontik.process._set_pipe_size = self._pipe_size_setter

    def test_pipe_buffer_overflow(self):
        upstreams = prepare_upstreams()
        num_workers = 1
        worker_state = WorkerState(Value(c_int, num_workers), Value(c_bool, 0), Lock())
        service_discovery = WorkerServiceDiscovery({})
        send_updates_hook: Optional[Callable] = None

        worker_queues = {'shared_data': Queue(1), 'enable_listener': Queue(1), 'worker_exit_event': Queue(1)}

        def master_after_fork_action(hook):
            nonlocal send_updates_hook
            send_updates_hook = hook

        def worker_function():
            worker_state.init_workers_count_down.value -= 1
            loop = asyncio.get_event_loop()
            loop.create_task(worker_teardown(worker_queues['worker_exit_event']))
            loop.run_forever()

        def worker_listener_handler(shared_upstreams):
            if worker_queues['shared_data'].full():
                worker_queues['shared_data'].get()
            worker_queues['shared_data'].put(shared_upstreams)

        # Case 1: no worker reads, make write overflow
        async def delayed_listener(*_args, **__kwargs):
            while True:
                await asyncio.sleep(0)
                with contextlib.suppress(Exception):
                    worker_queues['enable_listener'].get_nowait()
                    break
            await self._orig_listener(*_args, **__kwargs)

        frontik.process._worker_listener = delayed_listener

        fork_workers(
            worker_state=worker_state,
            num_workers=num_workers,
            master_before_fork_action=lambda: ({}, Lock()),
            master_after_fork_action=master_after_fork_action,
            master_before_shutdown_action=lambda: None,
            worker_function=worker_function,
            worker_listener_handler=worker_listener_handler,
        )
        if not worker_state.is_master:  # when worker stopes it should exit
            return

        assert send_updates_hook is not None
        service_discovery._upstreams.update(upstreams)
        for _i in range(500):
            send_updates_hook(get_upstream_bytes(service_discovery))

        assert bool(worker_state.resend_dict), 'resend dict should not be empty'

        # Case 2: wake up worker listener, check shared data is correct
        worker_queues['enable_listener'].put(True)
        time.sleep(1)
        worker_shared_data = worker_queues['shared_data'].get(timeout=2)
        assert len(worker_shared_data) == 1, 'upstreams size on master and worker should be the same'

        # Case 3: add new upstream, check worker get it
        service_discovery._upstreams['upstream2'] = Upstream(
            'upstream2',
            {},
            [Server('12.2.3.5', 'dest_host'), Server('12.22.3.5', 'dest_host')],
        )
        send_updates_hook(get_upstream_bytes(service_discovery))
        send_updates_hook(get_upstream_bytes(service_discovery))
        time.sleep(1)
        worker_shared_data = worker_queues['shared_data'].get(timeout=2)
        assert len(worker_shared_data) == 2, 'upstreams size on master and worker should be the same'

        worker_queues['worker_exit_event'].put(True)
