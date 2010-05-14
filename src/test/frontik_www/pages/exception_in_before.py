import frontik.handler

@frontik.handler.before
def fail_func(self, cb):

    def _cb(*args, **kw):
        raise Exception('oops')
        cb()

    self.get_url('http://ya.ru/', callback=_cb)

class Page(frontik.handler.PageHandler):
    @fail_func
    def get_page(self):
        self.doc.put('hello!')