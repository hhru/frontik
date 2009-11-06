import threading

from frontik.coev_impl.http_client import http_client

import coev
#coev.setdebug(True, coev.CDF_COEV)

def fun():
    print 111
    print http_client.fetch('127.0.0.1:8888')

worker = threading.Thread(target=fun)
worker.start()

coev.scheduler()
