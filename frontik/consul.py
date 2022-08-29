import sys
import asyncio
import warnings
import requests

import aiohttp
from aiohttp import ClientTimeout

from consul import base


PY_341 = sys.version_info >= (3, 4, 1)


class AsyncConsul(base.Consul):
    def __init__(self, *args, loop=None, **kwargs):
        self._loop = loop or asyncio.get_event_loop()
        super().__init__(*args, **kwargs)

    def http_connect(self, host, port, scheme, verify=True, cert=None):
        return _AsyncConsulHttpClient(host, port, scheme, loop=self._loop,
                                      verify=verify, cert=None)


class SyncConsul(base.Consul):
    @staticmethod
    def http_connect(host, port, scheme, verify=True, cert=None, timeout=None):
        return _SyncConsulHttpClient(host, port, scheme, verify, cert, timeout)


class _AsyncConsulHttpClient(base.HTTPClient):
    """Asyncio adapter for python consul using aiohttp library"""

    def __init__(self, *args, loop=None, **kwargs):
        super(_AsyncConsulHttpClient, self).__init__(*args, **kwargs)
        self._session = None
        self._loop = loop or asyncio.get_event_loop()

    async def _request(self, callback, method, uri, data=None, headers=None, total_timeout=None):
        connector = aiohttp.TCPConnector(loop=self._loop,
                                         verify_ssl=self.verify)
        async with aiohttp.ClientSession(connector=connector, timeout=ClientTimeout(total=total_timeout)) as session:
            self._session = session
            resp = await session.request(method=method,
                                         url=uri,
                                         data=data,
                                         headers=headers)
            body = await resp.text(encoding='utf-8')
            content = await resp.read()
            if resp.status == 599:
                raise base.Timeout
            r = base.Response(resp.status, resp.headers, body, content)
            await session.close()
            return callback(r)

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
        uri = self.uri(path, params)
        return await self._request(callback, 'GET', uri, headers=headers, total_timeout=total_timeout)

    async def put(self, callback, path, params=None, data='', headers=None):
        uri = self.uri(path, params)
        return await self._request(callback,
                                   'PUT',
                                   uri,
                                   data=data,
                                   headers=headers)

    async def delete(self, callback, path, params=None, data='', headers=None):
        uri = self.uri(path, params)
        return await self._request(callback,
                                   'DELETE',
                                   uri,
                                   data=data,
                                   headers=headers)

    async def post(self, callback, path, params=None, data='', headers=None):
        uri = self.uri(path, params)
        return await self._request(callback,
                                   'POST',
                                   uri,
                                   data=data,
                                   headers=headers)

    async def close(self):
        await self._session.close()


class _SyncConsulHttpClient(base.HTTPClient):
    def __init__(self, *args, **kwargs):
        super(_SyncConsulHttpClient, self).__init__(*args, **kwargs)
        self.session = requests.session()

    @staticmethod
    def response(response):
        response.encoding = 'utf-8'
        return base.Response(
            response.status_code,
            response.headers,
            response.text,
            response.content)

    def get(self, callback, path, params=None, headers=None, total_timeout=None):
        uri = self.uri(path, params)
        return callback(self.response(
            self.session.get(uri,
                             headers=headers,
                             verify=self.verify,
                             cert=self.cert,
                             timeout=self.timeout)))

    def put(self, callback, path, params=None, data='', headers=None):
        uri = self.uri(path, params)
        return callback(self.response(
            self.session.put(uri,
                             data=data,
                             headers=headers,
                             verify=self.verify,
                             cert=self.cert,
                             timeout=self.timeout)))

    def delete(self, callback, path, params=None, data='', headers=None):
        uri = self.uri(path, params)
        return callback(self.response(
            self.session.delete(uri,
                                data=data,
                                headers=headers,
                                verify=self.verify,
                                cert=self.cert,
                                timeout=self.timeout)))

    def post(self, callback, path, params=None, headers=None, data=''):
        uri = self.uri(path, params)
        return callback(self.response(
            self.session.post(uri,
                              data=data,
                              headers=headers,
                              verify=self.verify,
                              cert=self.cert,
                              timeout=self.timeout)))
