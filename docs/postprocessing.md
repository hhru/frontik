## Postprocessing

Postprocessing is a mechanism for final modifications to be applied to a response. The most obvious use-case is
replacing translation placeholders with real localized values.

Postprocessor can be added at any stage of request hanldling:

```python
self.add_postprocessor(postprocessor)
```

where ```postprocessor``` is a callable:

```python
def postprocessor(handler, response, callback):
    return None
```

```callback``` must be called when the work is done, with the result of postprocessing as an only argument.
Postprocessing can also be interrupted by throwing an exception or just calling ```self.redirect``` or
```self.finish()``` — this would explicitly generate the response.

Postprocessors are executed one after another in the order of their addition. Default postprocessor is set from the
```postprocessor``` variable of the application config file (see [Configuring application](docs/configure-app.md)).
