import time

import tornado.httpclient
import tornado.ioloop

import frontik.util

data, ct = frontik.util.make_mfd({}, {'1' : [{'filename':'1', 'body':'x'*1000 }]})

client = tornado.httpclient.AsyncHTTPClient()

req = tornado.httpclient.HTTPRequest(url='localhost:11111/', method='POST', body=data, headers={'Content-Type':ct, 'Content-Length':len(data)})

def hooray(*args, **kw):
    print time.time()

print time.time()

for i in range(10):
    client.fetch(req, hooray)

io = tornado.ioloop.IOLoop.instance()
io.start()
