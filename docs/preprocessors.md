## Preprocessors

Deprecated, see https://github.com/hhru/frontik/blob/master/docs/dependency_injection.md

The first step of page generation is preprocessing. Preprocessors are simple functions, which run after
`RequestHandler.prepare` and before handler code is executed. Preprocessors are great for running common actions
before actual request processing takes place.

Here is what a preprocessor may look like:

```python
from frontik.preprocessors import preprocessor


@preprocessor
def auth_preprocessor(handler):
    user_cookie = handler.get_cookie('user')
    if not is_authenticated(user_cookie):
        raise HTTPError(403, 'unauthorized user')


class Page(PageHandler):
    preprocessors = (auth_preprocessor,)

    # This also works
    # @auth_preprocessor
    def get_page(self):
        self.json.put({'result': 'OK'})
```

Preprocessors are defined in `preprocessors` attribute of `PageHandler` or as decorators for a particular handler method.
They are executed in order of declaration. Each preprocessor is converted to `tornado.gen.coroutine`, so they can be
asynchronous:

```python
@preprocessor
def auth_preprocessor(handler):
    user_cookie = handler.get_cookie('user')
    auth_result = yield handler.get_url('/auth-server', data={'user': user_cookie})
    
    if auth_result.response.error:
        raise HTTPError(403, 'unauthorized user')
```

You can break the chain of preprocessors execution by raising exceptions, calling methods that generate response immediately
like `handler.finish` or `handler.redirect` or by explicitly calling `handler.abort_preprocessors` method.

You can mix preprocessors defined in handler attribute and preprocessors specified as decorators:

```python
from frontik.handler import PageHandler

class Page(PageHandler):
    preprocessors = (first_preprocessor, second_preprocessor)

    def get_page(self):
        pass

    @third_preprocessor
    @fourth_preprocessor
    def post_page(self):
        pass
```

Preprocessors defined in handler attribute are executed first.
