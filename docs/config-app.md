## Configuring Frontik application

These parameters are specific to each Frontik application and could be defined in `config.py` file in the
root directory of the application (see [Frontik application structure](/docs/frontik-app.md)).

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
