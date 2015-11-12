## Running Frontik

Frontik server is easy to start from application code:

```python
frontik.server.main(config_file='/path/to/config.file')
```

where `config.file` must contain at least `app` parameter (see [Configuring Frontik](/docs/config.md)).

You could launch your application using `/usr/bin/frontik` script as well:

```shell
/usr/bin/frontik --app=application.package --config=/path/to/config.file
```

Configuration options can be set through command line or configuration file.
For description of all available config options see [Configuring Frontik](/docs/config.md)

For an example of a simple launcher that can be used in development environment, see [example-run.py](/examples/example-run.py).
It uses [examples/frontik.cfg](/examples/frontik.cfg) config file to launch a simple application.

A launcher from [frontik.server.supervisor](https://github.com/hhru/frontik/blob/master/frontik/server/supervisor.py)
module is used to run and control Frontik instances in production.

For information about Frontik applications, refer to [Frontik application structure](/docs/frontik-app.md).
