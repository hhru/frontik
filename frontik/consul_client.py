from __future__ import annotations

import asyncio
import sys
import warnings
from typing import TYPE_CHECKING

import aiohttp
import requests
from aiohttp import ClientTimeout
from consul import base

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from collections.abc import Callable
    from typing import Any

PY_341 = sys.version_info >= (3, 4, 1)

HTTP_METHOD_GET = "GET"
HTTP_METHOD_POST = "POST"
HTTP_METHOD_PUT = "PUT"
HTTP_METHOD_DELETE = "DELETE"


class ClientEventCallback:
    def on_http_request_success(self, method: str, path: str, response_code: int) -> None:
        pass

    def on_http_request_failure(self, method: str, path: str, ex: BaseException) -> None:
        pass

    def on_http_request_invalid(self, method: str, path: str, response_code: int) -> None:
        pass


class ConsulClient(base.Consul):
    def __init__(self, *args: Any, client_event_callback: ClientEventCallback | None = None, **kwargs: Any) -> None:
        self._client_event_callback = ClientEventCallback() if client_event_callback is None else client_event_callback
        super().__init__(*args, **kwargs)


class AsyncConsulClient(ConsulClient):
    def __init__(
        self,
        *args: Any,
        loop: AbstractEventLoop | None = None,
        client_event_callback: ClientEventCallback | None = None,
        **kwargs: Any,
    ) -> None:
        self._loop: AbstractEventLoop = loop or asyncio.get_event_loop()
        super().__init__(*args, client_event_callback=client_event_callback, **kwargs)

    def http_connect(self, host, port, scheme, verify=True, cert=None):
        return _AsyncConsulHttpClient(
            host,
            port,
            scheme,
            loop=self._loop,
            verify=verify,
            cert=None,
            client_event_callback=self._client_event_callback,
        )


class SyncConsulClient(ConsulClient):
    def http_connect(self, host, port, scheme, verify=True, cert=None, timeout=None):
        return _SyncConsulHttpClient(
            host,
            port,
            scheme,
            verify,
            cert,
            timeout,
            client_event_callback=self._client_event_callback,
        )


# this implementation was copied from https://github.com/hhru/python-consul2/blob/master/consul/aio.py#L16
# and then _client_event_callback was added
class _AsyncConsulHttpClient(base.HTTPClient):
    """Asyncio adapter for python consul using aiohttp library"""

    def __init__(
        self,
        *args: Any,
        loop: AbstractEventLoop | None = None,
        client_event_callback: ClientEventCallback,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._session: aiohttp.ClientSession | None = None
        self._loop = loop or asyncio.get_event_loop()
        self._client_event_callback: ClientEventCallback = client_event_callback

    async def _request(
        self,
        callback: Callable,
        method: str,
        path: str,
        params: dict | None = None,
        data: Any = None,
        headers: Any = None,
        total_timeout: float | None = None,
    ) -> Any:
        uri = self.uri(path, params)
        connector = aiohttp.TCPConnector(loop=self._loop, verify_ssl=self.verify)
        async with aiohttp.ClientSession(connector=connector, timeout=ClientTimeout(total=total_timeout)) as session:
            self._session = session
            try:
                resp = await session.request(method=method, url=uri, data=data, headers=headers)
                body = await resp.text(encoding='utf-8')
                content = await resp.read()
                r = base.Response(resp.status, resp.headers, body, content)
                await session.close()

                try:
                    if resp.status == 599:
                        raise base.Timeout()
                    result = callback(r)
                    self._client_event_callback.on_http_request_success(method, path, r.code)
                    return result
                except base.ConsulException as ex:
                    self._client_event_callback.on_http_request_invalid(method, path, r.code)
                    raise ex
            except Exception as ex:
                self._client_event_callback.on_http_request_failure(method, path, ex)
                raise ex

    # python prior 3.4.1 does not play nice with __del__ method
    if PY_341:  # pragma: no branch

        def __del__(self):
            warnings.warn("Unclosed connector in aio.Consul.HTTPClient", ResourceWarning)
            if self._session and not self._session.closed:
                warnings.warn("Unclosed connector in aio.Consul.HTTPClient", ResourceWarning)
                asyncio.ensure_future(self.close())

    async def get(self, callback, path, params=None, headers=None, total_timeout=None):
        return await self._request(
            callback,
            HTTP_METHOD_GET,
            path,
            params,
            headers=headers,
            total_timeout=total_timeout,
        )

    async def put(self, callback, path, params=None, data='', headers=None):
        return await self._request(callback, HTTP_METHOD_PUT, path, params, data, headers)

    async def delete(self, callback, path, params=None, data='', headers=None):
        return await self._request(callback, HTTP_METHOD_DELETE, path, params, data, headers)

    async def post(self, callback, path, params=None, data='', headers=None):
        return await self._request(callback, HTTP_METHOD_POST, path, params, data, headers)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


# this implementation was copied from https://github.com/hhru/python-consul2/blob/master/consul/std.py#L8
# and then _client_event_callback was added
class _SyncConsulHttpClient(base.HTTPClient):
    def __init__(self, *args: Any, client_event_callback: ClientEventCallback, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._session = requests.session()
        self._client_event_callback: ClientEventCallback = client_event_callback

    @staticmethod
    def response(response: requests.Response) -> base.Response:
        response.encoding = 'utf-8'
        return base.Response(response.status_code, response.headers, response.text, response.content)

    def _request(
        self,
        callback: Callable,
        method: str,
        path: str,
        params: dict | None = None,
        data: Any = None,
        headers: Any = None,
        total_timeout: float | None = None,
    ) -> Any:
        uri = self.uri(path, params)
        try:
            resp = self.response(
                self._session.request(
                    method=method,
                    url=uri,
                    data=data,
                    headers=headers,
                    verify=self.verify,
                    cert=self.cert,
                    timeout=self.timeout,
                ),
            )

            try:
                result = callback(resp)
                self._client_event_callback.on_http_request_success(method, path, resp.code)
                return result
            except base.ConsulException as ex:
                self._client_event_callback.on_http_request_invalid(method, path, resp.code)
                raise ex
        except Exception as ex:
            self._client_event_callback.on_http_request_failure(method, path, ex)
            raise ex

    def get(self, callback, path, params=None, headers=None, total_timeout=None):
        return self._request(callback, HTTP_METHOD_GET, path, params, headers=headers, total_timeout=total_timeout)

    def put(self, callback, path, params=None, data='', headers=None):
        return self._request(callback, HTTP_METHOD_PUT, path, params, data, headers)

    def delete(self, callback, path, params=None, data='', headers=None):
        return self._request(callback, HTTP_METHOD_DELETE, path, params, data, headers)

    def post(self, callback, path, params=None, headers=None, data=''):
        return self._request(callback, HTTP_METHOD_POST, path, params, data, headers)
