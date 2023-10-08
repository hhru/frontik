from __future__ import annotations

import collections
import socket
import threading
import time
from functools import partial
from typing import TYPE_CHECKING

from frontik.integrations import Integration, integrations_logger

if TYPE_CHECKING:
    from asyncio import Future
    from collections.abc import Callable, ItemsView
    from typing import Any

    from frontik.app import FrontikApplication
    from frontik.options import Options


class StatsdIntegration(Integration):
    def __init__(self):
        self.statsd_client = None

    def initialize_app(self, app: FrontikApplication) -> Future | None:
        self.statsd_client = app.statsd_client
        return None

    def initialize_handler(self, handler):
        handler.statsd_client = self.statsd_client


def _convert_tag(name: str, value: Any) -> str:
    return '{}_is_{}'.format(name.replace('.', '-'), str(value).replace('.', '-'))


def _convert_tags(tags: dict[str, Any]) -> str:
    if not tags:
        return ''

    return '.' + '.'.join(_convert_tag(name, value) for name, value in tags.items() if value is not None)


def _encode_str(some: str | bytes) -> bytes:
    return some if isinstance(some, bytes | bytearray) else some.encode('utf-8')


class Counters:
    def __init__(self) -> None:
        self._tags_to_counter: dict[tuple, int] = {}

    def add(self, value: int, **kwargs: Any) -> None:
        tags = tuple(sorted(kwargs.items()))
        self._tags_to_counter.setdefault(tags, 0)
        self._tags_to_counter[tags] += value

    def get_snapshot_and_reset(self) -> ItemsView:
        snapshot = self._tags_to_counter
        self._tags_to_counter = {}
        return snapshot.items()


class StatsDClientStub:
    def __init__(self) -> None:
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
    def __init__(
        self,
        host: str,
        port: int,
        default_periodic_send_interval_sec: int,
        app: str | None = None,
        max_udp_size: int = 508,
        reconnect_timeout: int = 2,
    ) -> None:
        self.host = host
        self.port = port
        self.default_periodic_send_interval_sec = default_periodic_send_interval_sec
        self.app = app
        self.max_udp_size = max_udp_size
        self.reconnect_timeout = reconnect_timeout
        self.buffer: collections.deque = collections.deque()
        self.stacking = False
        self.socket: socket.socket | None

        self._connect()

    def _connect(self) -> None:
        integrations_logger.info('statsd: connecting to %s:%d', self.host, self.port)

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(False)

        try:
            self.socket.connect((self.host, self.port))
        except OSError as e:
            integrations_logger.warning('statsd: connect error: %s', e)
            self._close()

    def _close(self) -> None:
        if self.socket is not None:
            self.socket.close()
        self.socket = None
        threading.Timer(self.reconnect_timeout, self._connect).start()

    def _send(self, message: str) -> None:
        if len(message) > self.max_udp_size:
            integrations_logger.debug('statsd: message %s is too long, dropping', message)

        if self.stacking:
            self.buffer.append(message)
            return

        self._write(message)

    def _write(self, data: bytes | str) -> None:
        if self.socket is None:
            integrations_logger.debug('statsd: trying to write to closed socket, dropping')
            return

        try:
            self.socket.send(_encode_str(data))
        except OSError as e:
            integrations_logger.warning('statsd: writing error: %s', e)
            self._close()

    def stack(self) -> None:
        self.buffer.clear()
        self.stacking = True

    def flush(self) -> None:
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

    def count(self, aspect: str, delta: int, **kwargs: Any) -> None:
        self._send(f'{aspect}{_convert_tags(dict(kwargs, app=self.app))}:{delta}|c')

    def counters(self, aspect: str, counters: Counters) -> None:
        for tags, count in counters.get_snapshot_and_reset():
            self.count(aspect, count, **dict(tags))

    def time(self, aspect: str, value: float, **kwargs: Any) -> None:
        self._send(f'{aspect}{_convert_tags(dict(kwargs, app=self.app))}:{value}|ms')

    def gauge(self, aspect: str, value: float, **kwargs: Any) -> None:
        self._send(f'{aspect}{_convert_tags(dict(kwargs, app=self.app))}:{value}|g')

    def send_periodically(self, callback: Callable, send_interval_sec: float | None = None) -> None:
        if send_interval_sec is None:
            send_interval_sec = self.default_periodic_send_interval_sec
        threading.Thread(target=partial(self._send_periodically, callback, send_interval_sec), daemon=True).start()

    @staticmethod
    def _send_periodically(callback: Callable, send_interval_sec: float) -> None:
        while True:
            try:
                time.sleep(send_interval_sec)
                callback()
            except Exception as e:
                integrations_logger.warning('statsd: writing error: %s', e)


def create_statsd_client(options: Options, app: FrontikApplication) -> StatsDClient | StatsDClientStub:
    statsd_client: StatsDClient | StatsDClientStub
    if options.statsd_host is None or options.statsd_port is None:
        statsd_client = StatsDClientStub()
        integrations_logger.info('statsd integration is disabled: statsd_host / statsd_port options are not configured')
    else:
        statsd_client = StatsDClient(
            options.statsd_host,
            options.statsd_port,
            options.statsd_default_periodic_send_interval_sec,
            app=app.app,
        )
    return statsd_client
