# coding=utf-8

from lxml import etree

import frontik.handler


class Page(frontik.handler.PageHandler):
    def get_page(self):
        end = self.finish_group.add(lambda: None)

        def job():
            return self.get_argument('nofail')

        def job_cb(future):
            self.doc.put(etree.Element('ok', result=future.result()))
            end()

        future = self.xml.executor.submit(job)
        self.add_future(future, self.check_finished(job_cb))
