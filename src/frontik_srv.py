#!/usr/bin/python
# -*- coding: utf-8 -*-

import frontik.server

from tornado.options import options

if __name__ == '__main__':
    frontik.server.bootstrap()
    frontik.server.main(options.host, options.port, options.autoreload)
