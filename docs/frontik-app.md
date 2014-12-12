## Frontik application structure

Each Frontik instance serves one application, which is imported from a package specified in
`app` parameter (see [Running Frontik](/docs/running.md)).

Frontik application is a set of files, organized in the following structure
(where `app` is a root folder for an application):

```
- app/
  |-- __init__.py
  |-- pages/
    |-- __init__.py
    |-- articles.py
    |-- some_other_module.py
  |-- config.py
```

Frontik application can contain a file named `config.py`. It is executed once at application startup
and can contain custom application initialization code.

Global variables from `config.py` are accessible from `PageHandler` instances via `self.config` attribute.

There are also certain global variables that you can set in `config.py`. For the list of such configuration parameters,
see [Configuring Frontik application](/docs/config-app.md).

Frontik application must contain a `pages` module, containing application controllers. By default, routing mechanism
will try to match each url to the file within `pages` module, but this can be overrided. For more information, see
[Routing in Frontik applications](/docs/routing.md)).
