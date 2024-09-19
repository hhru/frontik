from __future__ import annotations

from typing import Mapping

from tornado import httputil
from tornado.httputil import HTTPHeaders

from frontik import request_context
from frontik.version import version as frontik_version


class FrontikResponse:
    def __init__(
        self,
        status_code: int,
        headers: dict[str, str] | None | HTTPHeaders = None,
        body: bytes = b'',
        reason: str | None = None,
    ):
        self.headers = HTTPHeaders(get_default_headers())  # type: ignore

        if isinstance(headers, HTTPHeaders):
            for k, v in headers.get_all():
                self.headers.add(k, v)
        elif headers is not None:
            self.headers.update(headers)

        self.status_code = status_code
        self.body = body
        self._reason = reason
        self.data_written = False

    @property
    def reason(self) -> str:
        return self._reason or httputil.responses.get(self.status_code, 'Unknown')


def get_default_headers() -> Mapping[str, str | None]:
    request_id = request_context.get_request_id() or ''
    return {
        'Server': f'Frontik/{frontik_version}',
        'X-Request-Id': request_id,
    }
