## Postprocessing

Postprocessing is a mechanism for inserting and running hooks after finishing all page requests
(see [Making HTTP requests](/docs/http-client.md)).

Postprocessor can be added at any moment before finishing the main AsyncGroup:

```python
self.add_early_postprocessor(postprocessor)
self.add_late_postprocessor(postprocessor)
```

where `postprocessor` is a callable:

```python
def postprocessor(handler, callback):
    callback()
```

There are three types of postprocessors in Frontik:

__Early postprocessors__ are called just after all requests are done (the main AsyncGroup is finished). They are ideal
for general checks that can immediately interrupt request handling (for example make redirect or throw HTTPError) — in
such case no time would be wasted on templating and producing the response. Note that early postprocessing will be
skipped if any unhandled error occurs earlier.

__Late postprocessors__ are guaranteed to run at the very end of request handling (just before flushing the result).
You could use them in order to make last-minute amends to the response (for example, add headers or write something
useful to the log).

__Template postprocessors__ could be used for modifying the response text after the actual templating.
The most obvious use-case is replacing translation placeholders with real localized values.
Template postprocessor callable receives additional parameter containing the result of templating.

If any postprocessor fails, the page would be finished with an error.

```python
def tpl_postprocessor(handler, template, callback):
    callback(template.replace('foo', 'bar'))

self.add_template_postprocessor(postprocessor)
```

`callback` must be called when the work is done, with the result of postprocessing as an only argument.
Postprocessing can also be interrupted by throwing an exception or just calling `self.redirect` or
`self.finish()` methods, which explicitly generate the response.

Postprocessors are executed one after another in the order of their addition.
Default template postprocessor is set from the `postprocessor` variable of the application config file (see [Configuring application](/docs/config-app.md)).
