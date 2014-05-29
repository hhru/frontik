## Making HTTP requests

Frontik's [PageHandler](/frontik/handler.py) contains several methods for making HTTP requests to backends.

```python
def get_url(self, url, data=None, headers=None, connect_timeout=None, request_timeout=None,
            callback=None, follow_redirects=True, labels=None, add_to_finish_group=True,
            **params):
```

```python
def post_url(self, url, data='', headers=None, files=None, connect_timeout=None,
             request_timeout=None, callback=None, follow_redirects=True, content_type=None,
             labels=None, add_to_finish_group=True, **params):
```

```python
def put_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None,
            callback=None, content_type=None, labels=None, add_to_finish_group=True,
            **params):
```

```python
def delete_url(self, url, data='', headers=None, connect_timeout=None, request_timeout=None,
               callback=None, content_type=None, labels=None, add_to_finish_group=True,
               **params):
```

Method parameters are quite self-explaning. `**params` currently supports several keyword arguments:
* `parse_response` — if set to `True` (default), Frontik will try to parse the response body
(at the moment it supports XML and JSON content types) and pass the result alongside with the original response
to the `callback`. If set to `False`, the original response body string will be passed instead.
* `parse_on_error` — if set to `False` (default), Frontik will not parse the response body with
status code >= 300 and will pass `None` to the callback instead. To change this behaviour, set
`parse_on_error=True`.

Callback must have a following signature:

```python
def callback(parsed_response_body, response):
    pass
```

`labels` parameter is a list of debug labels to be assigned to this request, to be shown in debug mode.

All callbacks are always added to main [AsyncGroup](/frontik/async.py), `finish_group`,
except when `add_to_finish_group` parameter is set to `False`. Only after all requests and callbacks
have been finished, AsyncGroup is marked as finished and
[postprocessing](/docs/postprocessing.md) and [templating](/docs/producers.md) takes place.
