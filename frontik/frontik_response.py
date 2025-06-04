from typing import Optional, Union

from tornado import httputil
from tornado.httputil import HTTPHeaders

from frontik.request_integrations import request_context
from frontik.version import version as frontik_version


class FrontikResponse:
    def __init__(
        self,
        status_code: int,
        headers: Union[dict[str, str], None, HTTPHeaders] = None,
        body: bytes = b'',
        reason: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        self.headers = HTTPHeaders({
            'Server': f'Frontik/{frontik_version}',
            'X-Request-Id': request_id or request_context.get_request_id() or '',
        })

        if isinstance(headers, HTTPHeaders):
            for k, v in headers.get_all():
                self.headers.add(k, v)
        elif headers is not None:
            self.headers.update(headers)

        self.status_code = status_code
        self.body = body
        self._reason = reason
        self.headers_written = False

    @property
    def reason(self) -> str:
        return self._reason or httputil.responses.get(self.status_code, 'Unknown')

    def __repr__(self) -> str:
        return f'FrontikResponse(status_code={self.status_code}, headers={self.headers})'
