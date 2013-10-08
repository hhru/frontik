## Running Frontik

Frontik application is easy to run:

```python
frontik.server.main('/path/to/config.file')
```

All customization is made through config file. In the simplest case, you could leave it empty — there are sensible default values for all options.

[Tornado-util][tornado_util] module is used internally to run Frontik application.

[tornado_util]: https://github.com/hhru/tornado-util
