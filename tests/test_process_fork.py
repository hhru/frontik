import asyncio
import contextlib
import time
from ctypes import c_bool, c_int
from multiprocessing import Lock, Queue, Value

from http_client import options as http_client_options
from http_client.balancing import Server, Upstream, UpstreamConfig

import frontik.process
from frontik.options import options
from frontik.process import WorkerState, fork_workers
from frontik.service_discovery import UpstreamManager


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
            retry_policy={'403': {'idempotent': 'false'}, '500': {'idempotent': 'true'}},
        ),
    }
    return {
        'upstream': Upstream(
            'upstream', upstream_config, [Server('12.2.3.5', 'dest_host'), Server('12.22.3.5', 'dest_host')]
        )
    }


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
        control_master_state = {
            'shared_data': None,
            'worker_state': worker_state,
            'upstream_cache': None,
            'master_func_done': Queue(1),
        }
        control_worker_state = {'shared_data': Queue(1), 'enable_listener': Queue(1)}
        worker_exit_event = Queue(1)

        def master_function(shared_data, upstreams_lock, send_to_all_workers):
            shared_data.update(upstreams)
            upstream_cache = UpstreamManager(shared_data, None, upstreams_lock, send_to_all_workers, False, 'test')
            control_master_state['shared_data'] = shared_data
            control_master_state['upstream_cache'] = upstream_cache
            control_master_state['master_func_done'].put(True)

        def worker_function():
            control_master_state['worker_state'].init_workers_count_down.value -= 1
            loop = asyncio.get_event_loop()
            loop.create_task(worker_teardown(worker_exit_event))
            loop.run_forever()

        def worker_listener_handler(shared_data):
            if control_worker_state['shared_data'].full():
                control_worker_state['shared_data'].get()
            control_worker_state['shared_data'].put(shared_data)

        # Case 1: no worker reads, make write overflow
        async def delayed_listener(*_args, **__kwargs):
            while True:
                await asyncio.sleep(0)
                with contextlib.suppress(Exception):
                    control_worker_state['enable_listener'].get_nowait()
                    break
            await self._orig_listener(*_args, **__kwargs)

        frontik.process._worker_listener = delayed_listener

        fork_workers(
            worker_state=worker_state,
            num_workers=num_workers,
            worker_function=worker_function,
            master_function=master_function,
            master_before_shutdown_action=lambda: None,
            worker_listener_handler=worker_listener_handler,
        )
        if not worker_state.is_master:
            return

        control_master_state['master_func_done'].get(timeout=1)
        for _i in range(500):
            control_master_state['upstream_cache'].send_updates()

        resend_dict = control_master_state['worker_state'].resend_dict

        assert bool(resend_dict), 'resend dict should not be empty'

        # Case 2: wake up worker listener, check shared data is correct
        control_worker_state['enable_listener'].put(True)
        time.sleep(1)
        worker_shared_data = control_worker_state['shared_data'].get(timeout=2)
        assert len(worker_shared_data) == 1, 'upstreams size on master and worker should be the same'

        # Case 3: add new upstream, check worker get it
        control_master_state['shared_data']['upstream2'] = Upstream(
            'upstream2',
            {},
            [Server('12.2.3.5', 'dest_host'), Server('12.22.3.5', 'dest_host')],
        )
        control_master_state['upstream_cache'].send_updates()
        control_master_state['upstream_cache'].send_updates()
        time.sleep(1)
        worker_shared_data = control_worker_state['shared_data'].get(timeout=2)
        assert len(worker_shared_data) == 2, 'upstreams size on master and worker should be the same'

        worker_exit_event.put(True)
