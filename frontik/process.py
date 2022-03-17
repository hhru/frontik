import errno
import gc
import logging
import os
import signal
import sys
import time
import random
from dataclasses import dataclass

from tornado.options import options
from tornado.util import errno_from_exception

log = logging.getLogger('fork')


@dataclass
class State:
    server: bool
    children: dict
    terminating: bool


def fork_workers(worker_function, *, init_workers_count_down, num_workers, after_workers_up_action,
                 before_workers_shutdown_action):
    log.info("starting %d processes", num_workers)
    state = State(server=True, children={}, terminating=False)

    def sigterm_handler(signum, frame):
        if not state.server:
            return

        state.terminating = True
        before_workers_shutdown_action()
        for pid, id in state.children.items():
            log.info('sending %s to child %d (pid %d)', signal.Signals(signum).name, id, pid)
            os.kill(pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, sigterm_handler)
    signal.signal(signal.SIGINT, sigterm_handler)

    for i in range(num_workers):
        is_worker = _start_child(i, state)
        if is_worker:
            worker_function()
            return

    gc.enable()
    timeout = time.time() + options.init_workers_timeout_sec
    while init_workers_count_down.value > 0:
        if time.time() > timeout:
            raise Exception(
                f'workers did not started after {options.init_workers_timeout_sec} seconds,'
                f' do not started {init_workers_count_down.value} workers'
            )
        time.sleep(0.1)
    after_workers_up_action()
    _supervise_workers(state, worker_function)


def _supervise_workers(state, worker_function):
    while state.children:
        try:
            pid, status = os.wait()
        except OSError as e:
            if errno_from_exception(e) == errno.EINTR:
                continue
            raise

        if pid not in state.children:
            continue

        id = state.children.pop(pid)
        if os.WIFSIGNALED(status):
            log.warning("child %d (pid %d) killed by signal %d, restarting", id, pid, os.WTERMSIG(status))
        elif os.WEXITSTATUS(status) != 0:
            log.warning("child %d (pid %d) exited with status %d, restarting", id, pid, os.WEXITSTATUS(status))
        else:
            log.info("child %d (pid %d) exited normally", id, pid)
            continue

        if state.terminating:
            log.info("server is shutting down, not restarting %d", id)
            continue

        is_worker = _start_child(id, state)
        if is_worker:
            worker_function()
            return
    log.info('all children terminated, exiting')
    sys.exit(0)


def _start_child(i, state):
    # returns True inside child process, therwise False
    pid = os.fork()
    if pid == 0:
        state.server = False
        state.children = {}
        random.seed()
        return True
    else:
        state.children[pid] = i
        log.info('started child %d, pid=%d', i, pid)
        return False
