# coding=utf-8

import socket
import logging
import collections

from tornado.ioloop import IOLoop
from tornado.options import options

from frontik.compat import iteritems


statsd_logger = logging.getLogger('frontik.loggers.statsd')


def bootstrap_logger(app):
    if options.statsd_host is not None and options.statsd_port is not None:
        statsd_client = StatsDClient(options.statsd_host, options.statsd_port, app=app.app)
    else:
        statsd_client = StatsDClientStub()

    app.statsd_client = statsd_client

    def logger_initializer(handler):
        handler.statsd_client = statsd_client

    return logger_initializer


def _convert_tag(name, value):
    return '{}_is_{}'.format(name.replace('.', '-'), str(value).replace('.', '-'))


def _convert_tags(tags):
    if not tags:
        return ''

    return '.' + '.'.join(_convert_tag(name, value) for name, value in iteritems(tags) if value is not None)


class StatsDClientStub(object):
    def __init__(self):
        pass

    def stack(self):
        pass

    def flush(self):
        pass

    def count(self, aspect, delta, **kwargs):
        pass

    def time(self, aspect, value, **kwargs):
        pass


class StatsDClient(object):
    def __init__(self, host, port, app=None, max_udp_size=508, reconnect_timeout=2):
        self.host = host
        self.port = port
        self.app = app
        self.max_udp_size = max_udp_size
        self.reconnect_timeout = reconnect_timeout
        self.buffer = collections.deque()
        self.stacking = False
        self.socket = None

        self._connect()

    def _connect(self):
        statsd_logger.info('connecting to %s:%d', self.host, self.port)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)

        try:
            self.socket.connect((self.host, self.port))
        except socket.error as e:
            statsd_logger.warning("connect error: %s", e)
            self._close()
            return

    def _close(self):
        self.socket.close()
        self.socket = None
        IOLoop.current().add_timeout(IOLoop.current().time() + self.reconnect_timeout, self._connect)

    def _send(self, message):
        if len(message) > self.max_udp_size:
            statsd_logger.debug('message {} is too long, dropping', message)

        if self.stacking:
            self.buffer.append(message)
            return

        self._write(message)

    def _write(self, data):
        if self.socket is None:
            statsd_logger.debug('trying to write to closed socket, dropping')
            return

        try:
            self.socket.send(data)
        except (socket.error, IOError, OSError) as e:
            statsd_logger.warning("writing error: %s", e)
            self._close()

    def stack(self):
        self.buffer.clear()
        self.stacking = True

    def flush(self):
        self.stacking = False

        if not self.buffer:
            return

        data = self.buffer.popleft()

        while self.buffer:
            message = self.buffer.popleft()

            if len(data) + len(message) < self.max_udp_size:
                data += '\n' + message
                continue

            self._write(data)
            data = message

        self._write(data)

    def count(self, aspect, delta, **kwargs):
        self._send('{}{}:{}|c'.format(aspect, _convert_tags(dict(kwargs, app=self.app)), delta))

    def time(self, aspect, value, **kwargs):
        self._send('{}{}:{}|ms'.format(aspect, _convert_tags(dict(kwargs, app=self.app)), value))
