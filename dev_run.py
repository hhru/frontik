#!/usr/bin/python
# -*- coding: utf-8 -*-

import tornado.options

from frontik.server import main

if __name__ == "__main__":
    main('./frontik_dev.cfg')
