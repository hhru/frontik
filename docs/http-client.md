## Making HTTP requests

Frontik uses [balancing client](https://github.com/hhru/balancing-http-client). You can get instance through special dependency:

```python
from frontik.balancing_client import HttpClientT
from frontik.routing import router

@router.post('/handler')
async def post_page(http_client: HttpClientT) -> None:
    result = await http_client.post_url('http://backend', request.url.path, fail_fast=True)
```

In legacy controllers frontik's [PageHandler](/frontik/handler.py) contains several methods for making HTTP requests to backends:
get_url, post_url, put_url, etc...

Method parameters are:
* `host` - either host name with protocol or [virtual host](/docs/http-balancing.md) for balancing requests
* `path` - path starting with leading slash
* `data` - dict with request params or request body in case of POST requests
* `headers` - dict with request headers
* `connect_timeout` - if present, overrides default connect timeout
* `request_timeout` - if present, overrides default request timeout
* `max_timeout_tries` - multiplier for request timeout allowing retrying 
* `follow_redirects` - allows http client to handle redirects
* `waited` - if set to False, main request handler will not wait this request to finish
* `idempotent` - only for POST request. Makes request idempotent.
* `parse_response` — if set to `True`, Frontik will try to parse the response body
(currently it supports XML and JSON content types) and pass parsed to result.data. If set to `False`, 
the original response body string will be passed instead of the parsed response.
* `parse_on_error` — if set to `False`, Frontik will not parse the response body with status code >= 300. 
To change this behaviour, set `parse_on_error=True`.


All requests are always added to main [AsyncGroup](/frontik/futures.py), `finish_group`,
except when `waited` parameter is set to `False`. Only after all requests
are finished, AsyncGroup is marked as completed and [postprocessing](/docs/postprocessing.md)
and [templating](/docs/producers.md) takes place.

When host parameter equals one of configured virtual hosts, request will be retried unless following criteria met:
1) Number of tries has exceeded `max_tries` value
2) Previous try resulted not in connect timeout or `retry_policy` forbids further tries based on status code and idempotence 
3) Time allowed for request to finish has been exceeded
