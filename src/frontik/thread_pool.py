import time
import functools
import threading
import Queue

import logging
log = logging.getLogger('frontik.jobs')


def worker(queue):
    while True:
        cb = queue.get()
        try:
            cb()
        except Exception, e:
            log.exception('something that shouldnt happen happend!')


class Executor(object):
    def __init__(self, pool_size=5):
        self.events = Queue.Queue()
        self.log = log

        self.workers = [threading.Thread(target=functools.partial(worker, self.events))
                        for i in range(5)]
        [i.setDaemon(True) for i in self.workers]
        [i.start() for i in self.workers]

    def queue_job(self, func):
        self.events.put(func)


executor = Executor()
