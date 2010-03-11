#coding:utf8

import time

import tornado.httpclient
import tornado.ioloop

import util

data, ct = util.make_mfd({"test": "ччч"}, {'1' : [{'filename':'1', 'body':'я'*1000 }], "2": [{'filename':'1.jpg', 'body':open("/usr/lib/openoffice/basis3.1/share/gallery/www-back/bathroom.jpg").read() }, {'filename':'1', 'body':'y'*1000 }]})
client = tornado.httpclient.AsyncHTTPClient()
req = tornado.httpclient.HTTPRequest(request_timeout=200, url='localhost:11111/', method='POST', body=data, headers={'Content-Type':ct, 'Content-Length':len(data)})

def hooray(*args, **kw):
    print args[0], time.time()

print time.time()

for i in range(10):
    client.fetch(req, hooray)

io = tornado.ioloop.IOLoop.instance()
io.start()
