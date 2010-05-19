import tornado.ioloop
import tornado.httpclient

import time
import weakref


class Fetch(object):
    def __init__(self):
        self.done = False


class FetchTimeout(Exception):
    def __init__(self, url):
        Exception.__init__(self, 'timeout')
        self.url = url

class TimeoutingHttpFetcher(object):
    def __init__(self, http_client):
        self.http_client = http_client

    def fetch(self, req, cb):
        finish_time = time.time() + req.request_timeout

        f = Fetch()

        def timeout_cb():
            if not f.done:
                f.done = True
                cb(tornado.httpclient.HTTPResponse(
                   req, 599,
                   error=FetchTimeout(req.url),
                   request_time=req.request_timeout))

        timeout = self.http_client.io_loop.add_timeout(finish_time, timeout_cb)

        def response_cb(resp):
            if not f.done:
                f.done = True
                self.http_client.io_loop.remove_timeout(timeout)
                cb(resp)

        self.http_client.fetch(req, response_cb)
