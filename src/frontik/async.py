# -*- coding: utf-8 -*-

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

    def __init__(self, finish_cb, log=log.debug):
        self.counter = 0
        self.finished = False
        self.finish_cb = finish_cb
        self.log = log

    def try_finish(self):
        if self.counter == 0 and not self.finished:
            self.log('finishing group with %s', self.finish_cb)
            self.finished = True

            try:
                self.finish_cb()
            finally:

                # prevent possible cycle references
                self.finish_cb = None
                self.log = None

    def add(self, intermediate_cb):
        assert(not self.finished)
        
        self.counter += 1

        def new_cb(*args, **kwargs):
            self.counter -= 1
            self.log('%s requests pending', self.counter)

            try:
                intermediate_cb(*args, **kwargs)
            finally:
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
