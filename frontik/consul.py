import sys
import asyncio
import warnings
import requests

import aiohttp
from aiohttp import ClientTimeout

from consul import base

PY_341 = sys.version_info >= (3, 4, 1)

HTTP_METHOD_GET = "GET"
HTTP_METHOD_POST = "POST"
HTTP_METHOD_PUT = "PUT"
HTTP_METHOD_DELETE = "DELETE"


class Consul(base.Consul):
    def __init__(self, *args, client_event_callback=None, **kwargs):
        self._client_event_callback = ClientEventCallback() if client_event_callback is None else client_event_callback
        super().__init__(*args, **kwargs)


class AsyncConsul(Consul):
    def __init__(self, *args, loop=None, client_event_callback=None, **kwargs):
        self._loop = loop or asyncio.get_event_loop()
        super().__init__(*args, client_event_callback=client_event_callback, **kwargs)

    def http_connect(self, host, port, scheme, verify=True, cert=None):
        return _AsyncConsulHttpClient(host, port, scheme, loop=self._loop, verify=verify, cert=None,
                                      client_event_callback=self._client_event_callback)


class SyncConsul(Consul):
    def http_connect(self, host, port, scheme, verify=True, cert=None, timeout=None):
        return _SyncConsulHttpClient(host, port, scheme, verify, cert, timeout,
                                     client_event_callback=self._client_event_callback)


class _AsyncConsulHttpClient(base.HTTPClient):
    """Asyncio adapter for python consul using aiohttp library"""

    def __init__(self, *args, loop=None, client_event_callback, **kwargs):
        super(_AsyncConsulHttpClient, self).__init__(*args, **kwargs)
        self._session = None
        self._loop = loop or asyncio.get_event_loop()
        self._client_event_callback = client_event_callback

    async def _request(self, callback, method, path, params=None, data=None, headers=None, total_timeout=None):
        uri = self.uri(path, params)
        connector = aiohttp.TCPConnector(loop=self._loop, verify_ssl=self.verify)
        async with aiohttp.ClientSession(connector=connector, timeout=ClientTimeout(total=total_timeout)) as session:
            self._session = session
            try:
                resp = await session.request(method=method,
                                             url=uri,
                                             data=data,
                                             headers=headers)
                body = await resp.text(encoding='utf-8')
                content = await resp.read()
                r = base.Response(resp.status, resp.headers, body, content)
                await session.close()

                try:
                    if resp.status == 599:
                        raise base.Timeout
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
            warnings.warn("Unclosed connector in aio.Consul.HTTPClient",
                          ResourceWarning)
            if self._session and not self._session.closed:
                warnings.warn("Unclosed connector in aio.Consul.HTTPClient",
                              ResourceWarning)
                asyncio.ensure_future(self.close())

    async def get(self, callback, path, params=None, headers=None, total_timeout=None):
        return await self._request(callback,
                                   HTTP_METHOD_GET,
                                   path, params,
                                   headers=headers,
                                   total_timeout=total_timeout)

    async def put(self, callback, path, params=None, data='', headers=None):
        return await self._request(callback,
                                   HTTP_METHOD_PUT,
                                   path,
                                   params,
                                   data,
                                   headers)

    async def delete(self, callback, path, params=None, data='', headers=None):
        return await self._request(callback,
                                   HTTP_METHOD_DELETE,
                                   path,
                                   params,
                                   data,
                                   headers)

    async def post(self, callback, path, params=None, data='', headers=None):
        return await self._request(callback,
                                   HTTP_METHOD_POST,
                                   path,
                                   params,
                                   data,
                                   headers)

    async def close(self):
        await self._session.close()


class _SyncConsulHttpClient(base.HTTPClient):
    def __init__(self, *args, client_event_callback, **kwargs):
        super(_SyncConsulHttpClient, self).__init__(*args, **kwargs)
        self._session = requests.session()
        self._client_event_callback = client_event_callback

    @staticmethod
    def response(response):
        response.encoding = 'utf-8'
        return base.Response(
            response.status_code,
            response.headers,
            response.text,
            response.content)

    def _request(self, callback, method, path, params=None, data=None, headers=None, total_timeout=None):
        uri = self.uri(path, params)
        try:
            resp = self.response(
                self._session.request(method=method,
                                      url=uri,
                                      data=data,
                                      headers=headers,
                                      verify=self.verify,
                                      cert=self.cert,
                                      timeout=self.timeout))

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
        return self._request(callback,
                             HTTP_METHOD_GET,
                             path,
                             params,
                             headers=headers,
                             total_timeout=total_timeout)

    def put(self, callback, path, params=None, data='', headers=None):
        return self._request(callback,
                             HTTP_METHOD_PUT,
                             path,
                             params,
                             data,
                             headers)

    def delete(self, callback, path, params=None, data='', headers=None):
        return self._request(callback,
                             HTTP_METHOD_DELETE,
                             path,
                             params,
                             data,
                             headers)

    def post(self, callback, path, params=None, headers=None, data=''):
        return self._request(callback,
                             HTTP_METHOD_POST,
                             path,
                             params,
                             data,
                             headers)


class ClientEventCallback:
    def on_http_request_success(self, method, path, response_code):
        pass

    def on_http_request_failure(self, method, path, ex):
        pass

    def on_http_request_invalid(self, method, path, response_code):
        pass
