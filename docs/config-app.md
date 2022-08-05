## Configuring Frontik application

These parameters can be set for a Frontik application, by passing them to FrontikApplication in `config` parameter.

The reason for having another config (besides Frontik configuration file: [Configuring Frontik](/docs/config.md))
is that sometimes it is desirable to provide a more advanced initialization logic.
Frontik configuration file is executed by `config_parser.parse_config_file` function, which uses `exec` internally.
This sets some limitations, for example you can't use `__file__` constant in your code.
Application's config is free of this limitation.

If your application does not need any configuration, do not override FrontikApplication application_config method —
Frontik will start normally with default config.

| Option name            | Type   | Default value | Description                                           |
| ---------------------- | ------ | ------------- | ----------------------------------------------------- |
| `http_upstreams`       | `dict` | `None`        | [Virtual hosts](/docs/http-balancing.md) configuration|

`http_upstreams` example:

```python
http_upstreams = {
    'virtual_host_name': {'config': {'max_tries': 3}, 'servers': [{'server': 'http://localhost:1111', 'weight': 100}, {'server': 'http://localhost:2222', 'weight': 200}]},
}
```
