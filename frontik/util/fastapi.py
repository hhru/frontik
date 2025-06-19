from __future__ import annotations

from fastapi import Response

from frontik import media_types
from frontik.http_status import HTTP_REASON


def make_plain_response(status_code: int, message: str | None = None) -> Response:
    message = message or HTTP_REASON.get(status_code, 'Unknown')
    return Response(
        content=f'<html><title>{status_code}: {message}</title><body>{status_code}: {message}</body>',
        status_code=status_code,
        headers={'Content-Type': media_types.TEXT_HTML},
    )
