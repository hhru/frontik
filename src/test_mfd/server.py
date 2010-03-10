import time
import tornado.web
import tornado.ioloop
import tornado.httpserver

import logging
logging.basicConfig(level=logging.DEBUG)

class Acceptor(tornado.web.RequestHandler):
    def post(self):
        print time.time()

app = tornado.web.Application([('/', Acceptor)])

server = tornado.httpserver.HTTPServer(app)
server.listen(11111, '')

io = tornado.ioloop.IOLoop.instance()

io.start()
