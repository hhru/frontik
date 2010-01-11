#!/usr/bin/python
# -*- coding: utf-8 -*-

from tornado_util.supervisor import supervisor

supervisor(
    script='/usr/bin/frontik_srv.py',
    config='/etc/frontik/frontik.cfg'
)
