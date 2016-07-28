from lxml import etree
from tornado.ioloop import IOLoop

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):

        def job():
            return self.get_argument('nofail')

        @self.finish_group.add
        def job_cb(future):
            self.doc.put(etree.Element('ok', result=future.result()))

        IOLoop.current().add_future(self.xml.executor.submit(job), self.check_finished(job_cb))
