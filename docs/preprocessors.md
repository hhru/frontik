## Preprocessors

The first step of page generation is preprocessing. Preprocessors are simple functions, which run before
handler code is executed. Here is what a preprocessor may look like:

```python
from frontik.handler import PageHandler


def auth_preprocessor(handler, callback):
    user_cookie = handler.get_cookie('user')
    if authenticate(user_cookie):
        callback()
    else:
        raise HTTPError(403, 'unauthorized user')


class Page(PageHandler):
    preprocessors = (auth_preprocessor,)

    def get_page(self):
        self.json.put({'result': 'OK'})
```

Preprocessors are defined in `preprocessors` attribute of `PageHandler`. They are executed
in order of declaration. Each preprocessor should call the callback on its completion —
so preprocessors can be asynchronous:

```python
def auth_preprocessor(handler, callback):
    user_cookie = handler.get_cookie('user')

    def _cb(data, response):
        if not response.error:
            callback()
        else:
            raise HTTPError(403, 'unauthorized user')

    handler.get_url('/auth-server', data={'user': user_cookie}, callback=_cb)
```

If preprocessor doesn't call its callback, then preprocessing chain is broken and actual
handler code will not be executed.

It is also possible to define additional preprocessors for specific handler methods:

```python
from frontik.handler import PageHandler

class Page(PageHandler):
    preprocessors = (first_preprocessor, second_preprocessor)

    def get_page(self):
        # code skipped

    @PageHandler.add_preprocessor(third_preprocessor)
    def post_page(self):
        # code skipped
```

Common preprocessors will be executed first.

You can also use `PageHandler.add_preprocessor` as a decorator on preprocessors
to use preprocessors as decorators on handler methods:

```python
from frontik.handler import PageHandler


@PageHandler.add_preprocessor
def some_preprocessor(handler, callback):
    callback()


class Page(PageHandler):
    @some_preprocessor
    def get_page(self):
        # code skipped
```

Preprocessors are great for running common actions before actual request processing
takes place.
