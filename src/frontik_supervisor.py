#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import urllib2
import httplib
import logging
import time
import subprocess
import signal

import tornado.options
from tornado.options import options

def is_running(port):
    try:
        urllib2.urlopen('http://localhost:%s/status/' % (port,))
        return True
    except urllib2.URLError:
        return False
    except urllib2.HTTPError:
        return False

def start_worker(port):
    logging.debug('start worker %s', port)

    args = ['/usr/bin/frontik_srv.py', 
            '--port=%s' % (port,)]

    if options.logfile:
        args.append('--logfile=%s' % (options.logfile % dict(port=port),))

    if options.pidfile:
        args.append('--pidfile=%s' % (options.pidfile % dict(port=port),))
    
    return subprocess.Popen(args)

def stop_worker(port):
    logging.debug('stop worker %s', port)
    try:
        urllib2.urlopen('http://localhost:%s/stop/' % (port,))
    except urllib2.URLError:
        pass
    except httplib.BadStatusLine:
        pass

if __name__ == '__main__':
    tornado.options.define('start_port', 8000, int)
    tornado.options.define('workers_count', 4, int)
    tornado.options.define('start', False, bool)
    tornado.options.define('stop', False, bool)

    configs = tornado.options.parse_config_files(['/etc/frontik/frontik.cfg', 
                                                  './frontik_dev.cfg'])

    tornado.options.parse_command_line()

    logging.getLogger().setLevel(logging.DEBUG)
    tornado.options.enable_pretty_logging()

    if not (options.start or options.stop):
        logging.error('either --start or --stop should be present')
        sys.exit(1)

    def map_workers(f):
        return map(f, [options.start_port + p for p in range(options.workers_count)])

    def stop():
        if any(map_workers(is_running)):
            for i in range(3):
                logging.warning('some of the workers are running; trying to kill')
                map_workers(stop_worker)

                if not all(map_workers(is_running)):
                    break
            else:
                logging.warning('failed to stop workers')
                sys.exit(1)

    def start():
        map_workers(start_worker)

    if options.start:
        stop()
        start()

    if options.stop:
        stop()
