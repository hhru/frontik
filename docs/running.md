## Running Frontik

Frontik server is easy to run from application code:

```python
frontik.server.main(config_file='/path/to/config.file')
```

where `config.file` must contain at least `app` parameter (see [Configuring Frontik](/docs/config.md)).

You could launch your application using Frontik script as well:

```shell
/usr/bin/frontik --app=/path/to/application --config=/path/to/config.file
```

Configuration options can be set through command line or configuration file.
For description of all available config options see [Configuring Frontik](/docs/config.md)

For an example of a simple launcher that can be used in development environment, see [example-run.py](/examples/example-run.py).
It uses [examples/frontik.cfg](/examples/frontik.cfg) config file to launch a simple application.

Custom launcher from [tornado_util](https://github.com/hhru/tornado-util) module is used internally to run
and control Frontik servers instances.

For information about Frontik applications, refer to [Frontik application structure](/docs/frontik-app.md).
