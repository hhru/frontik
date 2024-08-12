## Postprocessing

Deprecated, works only in routes with `cls=PageHandler`. Use fastapi dependencies in new code

Postprocessing is a mechanism for inserting and running hooks after finishing all page requests
(see [Making HTTP requests](/docs/http-client.md)).

Postprocessor can be added at any moment before finishing the main AsyncGroup:

```python
self.add_postprocessor(postprocessor)
```

where `postprocessor` is a callable:

```python
def postprocessor(handler, callback):
    callback()
```

There are two types of postprocessors in Frontik:

![Postprocessing](/docs/postprocessing.png)

__Postprocessors__ are called just after all requests are done (the main AsyncGroup is finished). They are ideal
for general checks that can immediately interrupt request handling (for example make redirect or throw HTTPError).

__Template postprocessors__ could be used for modifying the response text after the actual templating.
One of the possible use-cases is replacing translation placeholders with real localized values.
Template postprocessor callable receives additional parameter containing the result of templating.

```python
def tpl_postprocessor(handler, template, callback):
    callback(template.replace('foo', 'bar'))

self.add_template_postprocessor(postprocessor)
```

`callback` for template postprocessor must be called with the result of postprocessing as an only argument
(callbacks for early and late postprocessors have no arguments).

Postprocessors are executed one after another in the order of their addition.
If any postprocessor throws an exception, the page would be finished with an error.
Postprocessing can also be interrupted by calling `self.redirect` or `self.finish`
methods, which explicitly generate the response.

If a postprocessor is not interrupted and does not call its callback either, the page will not be finished
and will freeze indefinitely.
