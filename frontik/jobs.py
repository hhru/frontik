import functools
import threading
import Queue
import logging

import tornado.ioloop
import tornado.options

jobs_log = logging.getLogger('frontik.jobs')


def _schedule_cb_result(cb, result):
    tornado.ioloop.IOLoop.instance().add_callback(functools.partial(cb, result))

return_result = _schedule_cb_result
reraise = _schedule_cb_result


def queue_worker(queue):
    while True:
        try:
            (prio, (func, cb, exception_cb)) = queue.get(timeout=10)
        except Queue.Empty:
            if tornado.options.options.warn_no_jobs:
                jobs_log.warn('No job in 10 secs')
            continue
        except Exception:
            jobs_log.exception('Cannot get new job')
            continue

        try:
            return_result(cb, func())
        except Exception, e:
            jobs_log.exception('Cannot perform job')
            reraise(exception_cb, e)


class IOLoopExecutor(object):
    @staticmethod
    def add_job(func, cb, exception_cb, prio=None):
        def __wrapper():
            try:
                cb(func())
            except Exception, e:
                exception_cb(e)

        tornado.ioloop.IOLoop.instance().add_callback(__wrapper)


class ThreadPoolExecutor(object):
    count = 0

    def __init__(self, pool_size):
        assert pool_size > 0
        self.events = Queue.PriorityQueue()

        jobs_log.debug('pool size: ' + str(pool_size))
        self.workers = [threading.Thread(target=functools.partial(queue_worker, self.events))
                        for i in range(pool_size)]
        [i.setDaemon(True) for i in self.workers]
        [i.start() for i in self.workers]
        jobs_log.debug('active threads count = ' + str(threading.active_count()))

    def add_job(self, func, cb, exception_cb, prio=10):
        try:
            ThreadPoolExecutor.count += 1
            self.events.put(((prio, ThreadPoolExecutor.count), (func, cb, exception_cb)))
        except Exception, e:
            jobs_log.exception('Cannot put job to queue')
            reraise(exception_cb, e)

_executor = None

def executor():
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(tornado.options.options.executor_pool_size)
    return _executor
