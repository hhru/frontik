import tornado.ioloop
import tornado.httpclient

import time
import weakref


class Fetch(object):
    def __init__(self, req, cb):
        self.req = req
        self.cb = cb
        self.done = False

    def timeout(self):
        if not self.done:
            self.done = True
            self.cb(tornado.httpclient.HTTPResponse(
                    self.req, 599,
                    error=tornado.httpclient.CurlError(None, 'timeout')))

    def response(self, resp):
        if not self.done:
            self.done = True
            self.cb(resp)


class TimeoutingHttpFetcher(object):
    def __init__(self, http_client):
        self.http_client = http_client

    def fetch(self, req, cb):
        finish_time = time.time() + req.request_timeout

        f = Fetch(req, cb)
        self.http_client.io_loop.add_timeout(finish_time, f.timeout)
        self.http_client.fetch(req, f.response)