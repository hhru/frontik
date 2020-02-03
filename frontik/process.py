import errno
import gc
import logging
import os
import signal
import sys

from tornado.util import errno_from_exception

log = logging.getLogger('fork')


def fork_workers(worker_function, *, num_workers, after_workers_up_action, before_workers_shutdown_action):
    log.info("starting %d processes", num_workers)
    children = {}
    is_worker = False
    for i in range(num_workers):
        is_worker = _start_child(i, children) is not None
        if is_worker:
            worker_function()
    if not is_worker:
        _supervise_workers(children, worker_function, after_workers_up_action, before_workers_shutdown_action)


def _supervise_workers(children, worker_function, after_workers_up_action, before_workers_shutdown_action):
    gc.enable()

    def sigterm_handler(signum, frame):
        before_workers_shutdown_action()
        for pid, id in children.items():
            log.info('sending SIGTERM to child %d (pid %d)', id, pid)
            os.kill(pid, signal.SIGTERM)
    signal.signal(signal.SIGTERM, sigterm_handler)

    after_workers_up_action()
    while children:
        try:
            pid, status = os.wait()
        except OSError as e:
            if errno_from_exception(e) == errno.EINTR:
                continue
            raise

        if pid not in children:
            continue

        id = children.pop(pid)
        if os.WIFSIGNALED(status):
            log.warning("child %d (pid %d) killed by signal %d, restarting", id, pid, os.WTERMSIG(status))
        elif os.WEXITSTATUS(status) != 0:
            log.warning("child %d (pid %d) exited with status %d, restarting", id, pid, os.WEXITSTATUS(status))
        else:
            log.info("child %d (pid %d) exited normally", id, pid)
            continue

        is_worker = _start_child(id, children) is not None
        if is_worker:
            worker_function()

    log.info('all children terminated, exiting')
    sys.exit(0)


def _start_child(i, children):
    pid = os.fork()
    if pid == 0:
        # we are child process - just return
        return i
    else:
        children[pid] = i
        log.info('started child %d, pid=%d', i, pid)
        return None
