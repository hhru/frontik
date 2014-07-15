## Running Frontik

Frontik server is easy to run:

```python
frontik.server.main(app='/path/to/application', config_file='/path/to/config.file')
```

or

```shell
/usr/bin/frontik --app=/path/to/application --config=/path/to/config.file
```

if Frontik is installed as a debian package.

All customization is made through the configuration file. In the simplest case, you could leave it empty — there are sensible
default values for all options. For description of all available config options see [Configuring Frontik](/docs/config.md)

For an example of a simple launcher that can be used in development environment, see [example-run.py](/examples/example-run.py).
It uses [examples/frontik.cfg](/examples/frontik.cfg) config file to launch a simple application.

Custom launcher from [tornado_util](https://github.com/hhru/tornado-util) module is used internally to run
and control Frontik servers instances.
