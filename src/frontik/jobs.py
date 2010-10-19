import time
import functools
import threading
import tornado.ioloop
io_loop = tornado.ioloop.IOLoop.instance()

import logging
log = logging.getLogger('frontik.jobs')

class _Job(threading.Thread):
    def __init__(self, func, done):
        threading.Thread.__init__(self)
        self.func = func
        self.result = None
        self.done = done

    def run(self):
        self.result = self.func()
        self.done.set()

class _Executor():
    def __init__(self):
        self.events = []

    def start_job(self, func, cb):
        done = threading.Event()
        job = _Job(func, done)
        def _cb():
            cb(job.result)
        job.start()
        self.events.append((done, _cb))
        self.listen_events()

    def listen_events(self):
#        log.debug('active threads count = ' + str(threading.active_count()))
        ev_c = len(self.events)
#        log.debug('waiting events count = ' + str(ev_c))
        if ev_c != 0:
#            io_loop.add_callback(self._event_listener)
            io_loop.add_timeout(time.time()+0.001, self._event_listener)

    def _event_listener(self):
        undone_events = filter(lambda (e, cb): not e.is_set(), self.events)
        if undone_events.count != self.events.count:
            done_events = filter(lambda (e, cb): e.is_set(), self.events)
            self.events = undone_events
            map(lambda (e, cb): cb(), done_events)
        self.listen_events()

executor = _Executor()
