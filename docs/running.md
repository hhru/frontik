## Running Frontik

Frontik server is easy to run:

```python
frontik.server.main('/path/to/config.file')
```

All customization is made through config file. In the simplest case, you could leave it empty — there are sensible
default values for all options. For description of all available config options see [Configuring Frontik](/docs/config.md)

In development environment you can use [dev_run.py](/dev_run.py) — a simple launcher, which uses ```frontik_dev.cfg```
as a config file, which you need to create or copy from [frontik_dev.cfg.ex](/frontik_dev.cfg.ex). The sample of a
production config can be found in [production/frontik.cfg](/production/frontik.cfg).

Custom launcher from [tornado_util](https://github.com/hhru/tornado-util) module is used internally to run
and control Frontik servers instances.

Frontik is an application server, so the next step is to learn about
[Frontik application structure](/docs/frontik-app.md).
