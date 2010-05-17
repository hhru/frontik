import Queue

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

    def release(self):
        assert (self.workers > 0)
        self.workers -= 1

        if not self.queue.empty():
            cb = self.queue.get()
            self.workers += 1
            cb()
