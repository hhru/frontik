import functools
import threading
import Queue
import tornado.ioloop
import tornado.options

import logging
log = logging.getLogger('frontik.jobs')

def work(func, cb, exception_cb):
    try:
        result = func()
        tornado.ioloop.IOLoop.instance().add_callback(functools.partial(cb, result))
    except Exception, e:
        tornado.ioloop.IOLoop.instance().add_callback(functools.partial(exception_cb, e))

def queue_worker(queue):
    while True:
        (prio, (func, cb, exception_cb)) = queue.get()
        work(func, cb, exception_cb)

class ThreadPoolExecutor(object):
    count = 0
    def __init__(self, pool_size=5):
        self.log = log
        self.events = Queue.PriorityQueue()

        self.log.debug('pool size: '+str(pool_size))
        self.workers = [threading.Thread(target=functools.partial(queue_worker, self.events))
                        for i in range(pool_size)]
        [i.setDaemon(True) for i in self.workers]
        [i.start() for i in self.workers]
        self.log.debug('active threads count = ' + str(threading.active_count()))

    def add_job(self, func, cb, exception_cb, prio=10):
        ThreadPoolExecutor.count += 1
        self.events.put(((prio, ThreadPoolExecutor.count), (func, cb, exception_cb)))

_executor =  None
def executor():
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(tornado.options.options.executor_pool_size)
    return _executor