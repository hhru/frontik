import time
import functools
import threading
import tornado.ioloop
io_loop = tornado.ioloop.IOLoop.instance()

import logging
log = logging.getLogger('frontik.jobs')

class Job(threading.Thread):
    def __init__(self, func, done):
        threading.Thread.__init__(self)
        self.func = func
        self.result = None
        self.done = done

    def run(self):
        self.result = self.func()
        self.done.set()

class Executor():
    def __init__(self, verbose = False, timeout = 0.001, log = log):
        self.events = []
        self.verbose = verbose
        self.timeout = timeout
        self.log = log

    def introduce_job(self, func, cb):
        done = threading.Event()
        job = Job(func, done)
        def _cb():
            cb(job.result)
        job.start()
        self.events.append((done, _cb))
        self.listen_events()

    def listen_events(self):
        if self.verbose: self.log.debug('active threads count = ' + str(threading.active_count()))
        ev_c = len(self.events)
        if self.verbose: self.log.debug('waiting events count = ' + str(ev_c))
        if ev_c != 0:
            if self.timeout is not None:
                io_loop.add_timeout(time.time()+self.timeout, self._event_listener)
            else:
                io_loop.add_callback(self._event_listener)


    def _event_listener(self):
        undone_events = filter(lambda (e, cb): not e.is_set(), self.events)
        if undone_events.count != self.events.count:
            done_events = filter(lambda (e, cb): e.is_set(), self.events)
            self.events = undone_events
            map(lambda (e, cb): cb(), done_events)
        self.listen_events()

executor = Executor()
