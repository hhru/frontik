## Running Frontik

Frontik application is easy to run:

```python
frontik.server.main('/path/to/config.file')
```

All customization is made through config file. In the simplest case, you could leave it empty — there are sensible
default values for all options.

In development environment you can use [dev_run.py](dev_run.py) — a simple launcher, which uses ```frontik_dev.cfg```
as a config file, which you need to create or copy from [frontik_dev.cfg.ex](frontik_dev.cfg.ex). The sample of a
production config can be found in [production/frontik.cfg](production/frontik.cfg).

[Tornado-util][tornado_util] module is used internally to run Frontik application.

[tornado_util]: https://github.com/hhru/tornado-util
