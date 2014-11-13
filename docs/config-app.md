## Configuring Frontik application

These parameters can be set for a Frontik application, in `config.py` file in the
root directory of the application (see [Frontik application structure](/docs/frontik-app.md)).

`config.py` is executed when the application is first loaded. The reason for having another config file (besides Frontik
configuration file: [Configuring Frontik](/docs/config.md)) is that sometimes it is desirable to provide a more advanced
initialization logic. Frontik configuration file is executed by `tornado.options.parse_config_file` function, which
uses `exec` internally. This sets some limitations, for example you can't use `__file__` constant in your code.
Application's `config.py` is free of this limitation.

If your application does not need any configuration, do not create `config.py` — Frontik will live normally without it.

| Option name            | Type   | Default value | Description                                           |
| ---------------------- | ------ | ------------- | ----------------------------------------------------- |
| `XSL_root`             | `str`  | `None`        | Root directory for XSL files                          |
| `XML_root`             | `str`  | `None`        | Root directory for XML files                          |
| `XSL_cache_limit`      | `int`  | `None`        | Upper limit for XSL LRU files cache                   |
| `XML_cache_limit`      | `int`  | `None`        | Upper limit for XML LRU files cache                   |
| `XSL_cache_step`       | `int`  | `None`        | Increase in weight for XSL cache entry after each get |
| `XML_cache_step`       | `int`  | `None`        | Increase in weight for XML cache entry after each get |
| `template_root`        | `str`  | `None`        | Root directory for Jinja templates                    |
| `template_cache_limit` | `int`  | `50`          | Upper limit for Jinja templates cache                 |
| `debug_labels`         | `dict` | `None`        | Debug labels for rich debug page, a dict of `label: color` values |

`debug_labels` option could contain something like this:

```python
debug_labels = {
    'READONLY': '#afa',
    'MASTER': '#ccf',
}
```

At the moment you can use these labels to annotate http requests (see [Making HTTP requests](/docs/http-client.md)).
