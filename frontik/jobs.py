import time
import functools
import threading
import Queue
import tornado.ioloop

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
        (func, cb, exception_cb) = queue.get()
        work(func, cb, exception_cb)


class PoolExecutor(object):
    def __init__(self, pool_size=5):
        self.log = log
        self.events = Queue.Queue()

        self.log.debug('pool size: '+str(pool_size))
        self.workers = [threading.Thread(target=functools.partial(queue_worker, self.events))
                        for i in range(pool_size)]
        [i.setDaemon(True) for i in self.workers]
        [i.start() for i in self.workers]
        self.log.debug('active threads count = ' + str(threading.active_count()))


    def add_job(self, func, cb, exception_cb):
        self.events.put((func, cb, exception_cb))

class SimpleSpawnExecutor(object):
    def __init__(self):
        self.log = log

    def add_job(self, func, cb, error_cb):
        threading.Thread(target=functools.partial(work, func, cb, error_cb)).start()
        self.log.debug('active threads count (+1) = ' + str(threading.active_count()))

class SimpleExecutor(object):
    def __init__(self):
        self.log = log

    def add_job(self, func, cb, error_cb):
            work(func, cb, error_cb)
