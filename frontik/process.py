import asyncio
import contextlib
import errno
import fcntl
import gc
import logging
import multiprocessing
import os
import pickle
import signal
import struct
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from multiprocessing.sharedctypes import Synchronized
from multiprocessing.synchronize import Lock as LockBase
from queue import Full, Queue
from threading import Lock, Thread
from typing import Any, Optional

from frontik.options import options
import shutil

log = logging.getLogger('fork')
multiprocessing.set_start_method('spawn', force=True)


F_SETPIPE_SZ = 1031  # can't use fcntl.F_SETPIPE_SZ on macos
PIPE_BUFFER_SIZE = 1000000
MESSAGE_HEADER_MAGIC = b'T1uf31f'
MESSAGE_SIZE_STRUCT = '=Q'
LISTENER_TASK = set()  # keep task from garbage collector


@dataclass
class WorkerState:
    init_workers_count_down: Synchronized
    master_done: Synchronized
    count_down_lock: LockBase
    is_master: bool = True
    children: dict = field(default_factory=lambda: {})  # pid: worker_id
    write_pipes: dict = field(default_factory=lambda: {})  # pid: write_pipe
    resend_dict: dict = field(default_factory=lambda: {})  # pid: flag
    terminating: bool = False
    single_worker_mode: bool = True


def fork_workers(
    *,
    worker_state: WorkerState,
    num_workers: int,
    master_function: Callable,
    master_before_shutdown_action: Callable,
    worker_function: Callable,
) -> None:
    log.info('starting %d processes', num_workers)
    worker_state.single_worker_mode = False

    def master_sigterm_handler(signum, _frame):
        if not worker_state.is_master:
            return

        worker_state.terminating = True
        master_before_shutdown_action()
        for pid, worker_id in worker_state.children.items():
            log.info('sending %s to child %d (pid %d)', signal.Signals(signum).name, worker_id, pid)
            os.kill(pid, signal.SIGTERM)

    signal.signal(signal.SIGTERM, master_sigterm_handler)
    signal.signal(signal.SIGINT, master_sigterm_handler)

    log.info('create dir: /tmp/my_consul')
    if os.path.exists('/tmp/my_consul'):
        shutil.rmtree('/tmp/my_consul')
    os.makedirs('/tmp/my_consul')
    log.info('dir /tmp/my_consul created, starting master thread')

    # worker_function_wrapped = partial(_worker_function_wrapper, worker_function)
    for worker_id in range(num_workers):
        is_worker = _start_child(worker_id, worker_state, worker_function)
        if is_worker:
            return

    gc.enable()
    timeout = time.time() + options.init_workers_timeout_sec
    while worker_state.init_workers_count_down.value > 0:
        if time.time() > timeout:
            for pid in worker_state.children:
                os.kill(pid, signal.SIGKILL)
            raise Exception(
                f'workers did not started after {options.init_workers_timeout_sec} seconds, do not started '
                f'{worker_state.init_workers_count_down.value} workers',
            )
        time.sleep(0.1)
    _master_function_wrapper(master_function)
    worker_state.master_done.value = True
    _supervise_workers(worker_state, worker_function, master_before_shutdown_action)


def _supervise_workers(
    worker_state: WorkerState, worker_function: Callable, master_before_shutdown_action: Callable
) -> None:
    while worker_state.children:
        try:
            pid, status = os.wait()
        except OSError as e:
            if _errno_from_exception(e) == errno.EINTR:
                continue
            raise

        if pid not in worker_state.children:
            continue

        worker_id = worker_state.children.pop(pid)

        try:
            worker_state.write_pipes.pop(pid).close()
        except Exception:
            log.warning('failed to close pipe for %d', pid)

        if os.WIFSIGNALED(status):
            log.warning('child %d (pid %d) killed by signal %d, restarting', worker_id, pid, os.WTERMSIG(status))

            # TODO remove this block # noqa
            master_before_shutdown_action()
            for pid, worker_id in worker_state.children.items():
                log.info('sending %s to child %d (pid %d)', signal.Signals(os.WTERMSIG(status)).name, worker_id, pid)
                os.kill(pid, signal.SIGTERM)
            log.info('all children terminated, exiting')
            time.sleep(options.stop_timeout)
            sys.exit(0)

        elif os.WEXITSTATUS(status) != 0:
            log.warning('child %d (pid %d) exited with status %d, restarting', worker_id, pid, os.WEXITSTATUS(status))
        else:
            log.info('child %d (pid %d) exited normally', worker_id, pid)
            continue

        if worker_state.terminating:
            log.info('server is shutting down, not restarting %d', worker_id)
            continue

        is_worker = _start_child(worker_id, worker_state, worker_function)
        if is_worker:
            return
    log.info('all children terminated, exiting')
    sys.exit(0)


# returns True inside child process, otherwise False
def _start_child(worker_id: int, worker_state: WorkerState, worker_function: Callable) -> bool:
    # it cannot be multiprocessing.pipe because we need to set nonblock flag and connect to asyncio

    prc = multiprocessing.Process(target=worker_function, args=(options, worker_state, worker_id))
    prc.start()
    pid = prc.pid

    worker_state.children[pid] = worker_id
    log.info('started child %d, pid=%d', worker_id, pid)
    return False


def _set_pipe_size(fd: int, worker_id: int) -> None:
    try:
        fcntl.fcntl(fd, F_SETPIPE_SZ, PIPE_BUFFER_SIZE)
    except OSError as ex:
        log.warning('failed to set pipe size for %d ex: %s', worker_id, ex)


def _errno_from_exception(e: BaseException) -> Optional[int]:
    if hasattr(e, 'errno'):
        return e.errno
    elif e.args:
        return e.args[0]
    else:
        return None


def _master_function_wrapper(master_function: Callable) -> None:
    data_for_share: dict = {}
    lock = Lock()

    master_function_thread = Thread(
        target=master_function,
        args=(data_for_share, lock, _send_to_all),
        daemon=True,
    )
    master_function_thread.start()
    log.info('master thread started')


def _send_to_all(data_raw: Any) -> None:
    fn = time.time()

    with open('/tmp/my_consul/' + str(fn), 'wb') as c_file:
        pickle.dump(data_raw, c_file)

    log.info(f'consul data written /tmp/my_consul/{fn}')
