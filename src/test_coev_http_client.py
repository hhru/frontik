import thread

import coev
coev.setdebug(module=True, library=coev.CDF_COEV)

import logging
logging.basicConfig(level=logging.DEBUG)

log = logging.getLogger()

#thread.start_new_thread(coev.scheduler, tuple())

#from frontik.coev_impl.http_client import http_client

def fun():
    print 111
    print http_client.fetch('127.0.0.1:8888')

#thread.start_new_thread(fun, tuple())

def test_fun():
    while True:
        print 111
        print coev.stall()

thread.start_new_thread(test_fun, tuple())

log.debug('start scheduler')
coev.scheduler()
#worker = threading.Thread(target=fun)
#worker.start()

