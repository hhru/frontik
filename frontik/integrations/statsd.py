import socket
import collections
import threading
import time
from functools import partial
from asyncio import Future
from typing import Optional

from frontik.integrations import Integration, integrations_logger
from frontik.options import options


class StatsdIntegration(Integration):
    def __init__(self):
        self.statsd_client = None

    def initialize_app(self, app) -> Optional[Future]:
        self.statsd_client = create_statsd_client(options, app)
        app.statsd_client = self.statsd_client
        return None

    def initialize_handler(self, handler):
        handler.statsd_client = self.statsd_client


def _convert_tag(name, value):
    return '{}_is_{}'.format(name.replace('.', '-'), str(value).replace('.', '-'))


def _convert_tags(tags):
    if not tags:
        return ''

    return '.' + '.'.join(_convert_tag(name, value) for name, value in tags.items() if value is not None)


def _encode_str(some):
    return some if isinstance(some, (bytes, bytearray)) else some.encode('utf-8')


class Counters:
    def __init__(self):
        self._tags_to_counter = {}

    def add(self, value, **kwargs):
        tags = tuple(sorted(kwargs.items()))
        self._tags_to_counter.setdefault(tags, 0)
        self._tags_to_counter[tags] += value

    def get_snapshot_and_reset(self):
        snapshot = self._tags_to_counter
        self._tags_to_counter = {}
        return snapshot.items()


class StatsDClientStub:
    def __init__(self):
        pass

    def stack(self):
        pass

    def flush(self):
        pass

    def count(self, aspect, delta, **kwargs):
        pass

    def counters(self, aspect, counters):
        pass

    def time(self, aspect, value, **kwargs):
        pass

    def gauge(self, aspect, value, **kwargs):
        pass

    def send_periodically(self, callback, send_interval_sec=None):
        pass


class StatsDClient:
    def __init__(self, host, port, default_periodic_send_interval_sec, app=None, max_udp_size=508, reconnect_timeout=2):
        self.host = host
        self.port = port
        self.default_periodic_send_interval_sec = default_periodic_send_interval_sec
        self.app = app
        self.max_udp_size = max_udp_size
        self.reconnect_timeout = reconnect_timeout
        self.buffer = collections.deque()
        self.stacking = False
        self.socket = None

        self._connect()

    def _connect(self):
        integrations_logger.info('statsd: connecting to %s:%d', self.host, self.port)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)

        try:
            self.socket.connect((self.host, self.port))
        except socket.error as e:
            integrations_logger.warning('statsd: connect error: %s', e)
            self._close()
            return

    def _close(self):
        self.socket.close()
        self.socket = None
        threading.Timer(self.reconnect_timeout, self._connect).start()

    def _send(self, message):
        if len(message) > self.max_udp_size:
            integrations_logger.debug('statsd: message %s is too long, dropping', message)

        if self.stacking:
            self.buffer.append(message)
            return

        self._write(message)

    def _write(self, data):
        if self.socket is None:
            integrations_logger.debug('statsd: trying to write to closed socket, dropping')
            return

        try:
            self.socket.send(_encode_str(data))
        except (socket.error, IOError, OSError) as e:
            integrations_logger.warning('statsd: writing error: %s', e)
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

    def counters(self, aspect, counters):
        for tags, count in counters.get_snapshot_and_reset():
            self.count(aspect, count, **dict(tags))

    def time(self, aspect, value, **kwargs):
        self._send('{}{}:{}|ms'.format(aspect, _convert_tags(dict(kwargs, app=self.app)), value))

    def gauge(self, aspect, value, **kwargs):
        self._send('{}{}:{}|g'.format(aspect, _convert_tags(dict(kwargs, app=self.app)), value))

    def send_periodically(self, callback, send_interval_sec=None):
        if send_interval_sec is None:
            send_interval_sec = self.default_periodic_send_interval_sec
        threading.Thread(target=partial(self._send_periodically, callback, send_interval_sec), daemon=True).start()

    @staticmethod
    def _send_periodically(callback, send_interval_sec):
        while True:
            try:
                time.sleep(send_interval_sec)
                callback()
            except Exception as e:
                integrations_logger.warning('statsd: writing error: %s', e)


def create_statsd_client(options, app):
    if options.statsd_host is None or options.statsd_port is None:
        statsd_client = StatsDClientStub()
        integrations_logger.info(
            'statsd integration is disabled: statsd_host / statsd_port options are not configured'
        )
    else:
        statsd_client = StatsDClient(options.statsd_host, options.statsd_port,
                                     options.statsd_default_periodic_send_interval_sec, app=app.app)
    return statsd_client
