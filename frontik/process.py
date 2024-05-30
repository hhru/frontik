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

log = logging.getLogger('fork')
multiprocessing.set_start_method('fork')


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
    worker_listener_handler: Callable,
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

    worker_function_wrapped = partial(_worker_function_wrapper, worker_function, worker_listener_handler)
    for worker_id in range(num_workers):
        is_worker = _start_child(worker_id, worker_state, worker_function_wrapped)
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
    _master_function_wrapper(worker_state, master_function)
    worker_state.master_done.value = True
    _supervise_workers(worker_state, worker_function_wrapped, master_before_shutdown_action)


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

            # TODO remove this block  # noqa
            worker_state.terminating = True
            master_before_shutdown_action()
            for pid, worker_id in worker_state.children.items():
                log.info('sending %s to child %d (pid %d)', signal.Signals(os.WTERMSIG(status)).name, worker_id, pid)
                os.kill(pid, signal.SIGTERM)

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
    read_fd, write_fd = os.pipe()
    os.set_blocking(read_fd, False)
    os.set_blocking(write_fd, False)

    prc = multiprocessing.Process(target=worker_function, args=(read_fd, write_fd, worker_state, worker_id))
    prc.start()
    pid = prc.pid

    os.close(read_fd)
    worker_state.children[pid] = worker_id
    _set_pipe_size(write_fd, worker_id)
    worker_state.write_pipes[pid] = os.fdopen(write_fd, 'wb')
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


def _worker_function_wrapper(worker_function, worker_listener_handler, read_fd, write_fd, worker_state, worker_id):
    os.close(write_fd)
    _set_pipe_size(read_fd, worker_id)
    gc.enable()
    worker_state.is_master = False

    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.stop()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    task = loop.create_task(_worker_listener(read_fd, worker_listener_handler))
    LISTENER_TASK.add(task)
    worker_function()


async def _worker_listener(read_fd: int, worker_listener_handler: Callable) -> None:
    stream = asyncio.StreamReader()
    fio = os.fdopen(read_fd)
    await asyncio.get_running_loop().connect_read_pipe(lambda: asyncio.StreamReaderProtocol(stream), fio)

    while True:
        try:
            await stream.readuntil(MESSAGE_HEADER_MAGIC)
            size_header = await stream.readexactly(8)
            (size,) = struct.unpack(MESSAGE_SIZE_STRUCT, size_header)
            data_raw = await stream.readexactly(size)
            log.debug('received data from master, length: %d', size)
            data = pickle.loads(data_raw)
            worker_listener_handler(data)
        except asyncio.IncompleteReadError as e:
            log.exception('master shared data pipe is closed')
            sys.exit(1)
        except Exception as e:
            log.exception('failed to fetch data from master %s', e)


def _master_function_wrapper(worker_state: WorkerState, master_function: Callable) -> None:
    data_for_share: dict = {}
    lock = Lock()

    resend_notification: Queue = Queue(maxsize=1)

    resend_thread = Thread(
        target=_resend,
        args=(worker_state, resend_notification, worker_state.resend_dict, lock, data_for_share),
        daemon=True,
    )
    resend_thread.start()

    send_to_all_workers = partial(_send_to_all, worker_state, resend_notification, worker_state.resend_dict)
    master_function_thread = Thread(
        target=master_function,
        args=(data_for_share, lock, send_to_all_workers),
        daemon=True,
    )
    master_function_thread.start()


def _resend(
    worker_state: WorkerState,
    resend_notification: Queue,
    resend_dict: dict[int, bool],
    lock: Lock,
    data_for_share: dict,
) -> None:
    while True:
        resend_notification.get()
        time.sleep(1.0)

        with lock:
            data = pickle.dumps(list(data_for_share.values()))
            clients = list(resend_dict.keys())
            if log.isEnabledFor(logging.DEBUG):
                client_ids = ','.join(map(str, clients))
                log.debug('sending data to %s length: %d', client_ids, len(data))
            resend_dict.clear()

            for worker_id in clients:
                pipe = worker_state.write_pipes.get(worker_id, None)

                if pipe is None:
                    continue

                # writing 2 times to ensure fix of client reading pattern
                _send_update(resend_notification, resend_dict, worker_id, pipe, data)
                _send_update(resend_notification, resend_dict, worker_id, pipe, data)


def _send_to_all(
    worker_state: WorkerState,
    resend_notification: Queue,
    resend_dict: dict[int, bool],
    data_raw: Any,
) -> None:
    data = pickle.dumps(data_raw)
    log.debug('sending data to all workers length: %d', len(data))
    for worker_pid, pipe in worker_state.write_pipes.items():
        _send_update(resend_notification, resend_dict, worker_pid, pipe, data)


def _send_update(
    resend_notification: Queue,
    resend_dict: dict[int, bool],
    worker_pid: int,
    pipe: Any,
    data: bytes,
) -> None:
    header_written = False
    try:
        pipe.write(MESSAGE_HEADER_MAGIC + struct.pack(MESSAGE_SIZE_STRUCT, len(data)))
        header_written = True
        pipe.write(data)
        pipe.flush()
    except BlockingIOError:
        log.warning('client %s pipe blocked', worker_pid)
        if header_written:
            resend_dict[worker_pid] = True
            with contextlib.suppress(Full):
                resend_notification.put_nowait(True)
    except Exception as e:
        log.exception('client %s pipe write failed  %s', worker_pid, e)
