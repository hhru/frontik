## Making HTTP requests

Frontik's [PageHandler](/frontik/handler.py) contains several methods for making HTTP requests to backends.

```python
def get_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None,
            callback=None, follow_redirects=True, parse_response=True, labels=None):
```

```python
def post_url(self, url, data='', headers=None, files=None, connect_timeout=None, request_timeout=None,
             follow_redirects=True, content_type=None, callback=None, parse_response=True,
             labels=None):
```

```python
def put_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None,
            callback=None, parse_response=True, labels=None):
```

```python
def delete_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None,
               callback=None, parse_response=True, labels=None):
```

Method parameters are quite self-explaning. If `parse_response` is `True`, Frontik will try to parse the response
body (at the moment it supports XML and JSON content types) and pass the result alongside with the original response
to the `callback`. If `parse_response` is `False`, the original response body string will be passed instead.

Callback must have a following signature:

```python
def callback(parsed_response_body, response):
    pass
```

`labels` parameter is a list of debug labels to be assigned to this request, to be shown in debug mode.

All callbacks are added to main [AsyncGroup](/frontik/async.py), `finish_group`.
Only after all requests and callbacks are finished, AsyncGroup is marked as finished and
[postprocessing](/docs/postprocessing.md) and [templating](/docs/producers.md) takes place.
