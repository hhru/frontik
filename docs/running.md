## Running Frontik

Frontik server is easy to start from application code:

```python
frontik.server.main(config_file='/path/to/config.file')
```

`config_file` argument can contain a path to the configuration file.
If `config_file` is set to `None` and `--config` option is missing from the command line, then Frontik will expect all
configuration options to be specified through command line.

The only mandatory configuration option is `app` option, specifying the name of Frontik application package.

For more details about configuration refer to [Configuring Frontik](/docs/config.md).

You could launch your application using [/usr/bin/frontik](/scripts/frontik) script as well:

```shell
/usr/bin/frontik --app=application.package --config=/path/to/config.file
```

For an example of a simple launcher that can be used in development environment, see [example-run.py](/examples/example-run.py).
It uses [examples/frontik.cfg](/examples/frontik.cfg) config file to launch a simple application.

A supervisor from [frontik.server.supervisor](/frontik/server/supervisor.py) module can be used to run and control
Frontik instances in production. For more information on the supervisor see [Using built-in supervisor](/docs/supervisor.md).

For information about Frontik applications, refer to [Frontik application structure](/docs/frontik-app.md).
