# -*- coding: utf-8 -*-

import time
import Queue

import logging
log = logging.getLogger('frontik.async')


def before(before_fun):
    '''
    before_fun :: f(self, cb)
    '''

    def before_fun_deco(fun):
        def new_fun(self, *args, **kw):
            def cb():
                fun(self, *args, **kw)
            before_fun(self, self.async_callback(cb))
        return new_fun
    return before_fun_deco


class AsyncGroup(object):
    '''
    Grouping of several async requests and final callback in such way, that final callback is invoked after the last
     request is finished.

    Frontik uses this class to find the right moment to finish page.
    '''

    # in the breaking compatibility version parameters should be
    # rearranged: name, finish_cb, log
    def __init__(self, finish_cb, log=log.debug, name=None):
        self.counter = 0
        self.finished = False
        self.finish_cb = finish_cb
        self.log_fun = log
        self.name = name

        self.start_time = time.time()
        self.finish_time = None

        if self.name is not None:
            self.log_name = '{0} group'.format(self.name)
        else:
            self.log_name = 'group'

    def log(self, msg, *args, **kw):
        self.log_fun(self.log_name + ": " + msg, *args, **kw)

    def finish(self):
        if not self.finished:
            self.finish_time = time.time()
            self.log('done in %.2fms', (self.finish_time - self.start_time)*1000.)
            self.finished = True

            try:
                self.finish_cb()
            finally:

                # prevent possible cycle references
                self.finish_cb = None

    def try_finish(self):
        if self.counter == 0:
            self.finish()

    def _inc(self):
        assert(not self.finished)
        self.counter += 1

    def _dec(self):
        self.counter -= 1
        self.log('%s requests pending', self.counter)

    def add(self, intermediate_cb):
        self._inc()

        def new_cb(*args, **kwargs):
            if not self.finished:
                try:
                    self._dec()
                    intermediate_cb(*args, **kwargs)
                finally:
                    self.try_finish()
            else:
                self.log("Ignoring response because of already finished group")

        return new_cb

    def add_notification(self):
        self._inc()

        def new_cb(*args, **kwargs):
            self._dec()
            self.try_finish()

        return new_cb


class AsyncWorkPool(object):
    '''
    AWP - machinery to limit the number of simultaneously working async processes
    add new task with .add_task(cb)
    let pool know when task is finished with .release()
    '''

    def __init__(self, pool_size):
        self.pool_size = pool_size
        self.workers = 0
        self.queue = Queue.Queue()

    def add_task(self, cb):
        if self.workers < self.pool_size:
            self.workers += 1
            cb()
        else:
            self.queue.put(cb)
            log.debug('postponing %s because worker pool is full; queue size = %s)', cb, self.queue.qsize())

    def release(self):
        assert (self.workers > 0)
        self.workers -= 1

        if not self.queue.empty():
            cb = self.queue.get()
            self.workers += 1
            log.debug('invoking postponed cb %s; queue size = %s', cb, self.queue.qsize())
            cb()
