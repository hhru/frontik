import errno
import gc
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass

from tornado.options import options
from tornado.util import errno_from_exception

log = logging.getLogger('fork')


@dataclass
class State:
    server: bool
    children: dict
    read_pipe: int
    write_pipes: dict
    terminating: bool


def fork_workers(worker_function, *, init_workers_count_down, num_workers, after_workers_up_action,
                 before_workers_shutdown_action, children_pipes):
    log.info("starting %d processes", num_workers)
    state = State(server=True, children={}, read_pipe=0, write_pipes=children_pipes, terminating=False)

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
            worker_function(state.read_pipe)
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

        try:
            state.write_pipes.pop(pid).close()
        except Exception:
            log.warning('failed to close pipe for %d', pid)

        if os.WIFSIGNALED(status):
            log.warning("child %d (pid %d) killed by signal %d, restarting", id, pid, os.WTERMSIG(status))
        elif os.WEXITSTATUS(status) != 0:
            log.warning("child %d (pid %d) exited with status %d, restarting", id, pid, os.WEXITSTATUS(status))
        else:
            log.info('child %d (pid %d) exited normally', id, pid)
            continue

        if state.terminating:
            log.info("server is shutting down, not restarting %d", id)
            continue

        is_worker = _start_child(id, state)
        if is_worker:
            worker_function(state.read_pipe)
            return
    log.info('all children terminated, exiting')
    sys.exit(0)


# returns True inside child process, otherwise False
def _start_child(i, state):
    read_fd, write_fd = os.pipe2(os.O_NONBLOCK)
    pid = os.fork()
    if pid == 0:
        os.close(write_fd)
        state.server = False
        state.read_pipe = read_fd
        state.write_pipes = {}
        state.children = {}
        return True
    else:
        os.close(read_fd)
        state.children[pid] = i
        state.write_pipes[pid] = os.fdopen(write_fd, 'wb')
        log.info('started child %d, pid=%d', i, pid)
        return False
