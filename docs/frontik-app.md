## Frontik application structure

Each Frontik instance serves one application, which is loaded from a directory given in
`app` parameter (see [Running Frontik](/docs/running.md)).

Frontik application is a set of files, organized in the following structure
(where `app` is a root folder for an application):

```
- app/
  |-- pages/
    |-- __index__py
    |-- articles.py
    |-- some_other_module.py
  |-- config.py
```

Frontik application can contain a (possibly empty) `config.py` file. It will be executed once at the start of
Frontik server and can contain custom application initialization code.

Global variables from `config.py` are accessible from `PageHandler` instances via `self.config` attribute.

There are also certain global variables that you can set in `config.py`. For the list of such configuration parameters,
see [Configuring Frontik application](/docs/config-app.md).

Frontik application must contain a `pages` module, containing application controllers. By default, routing mechanism
will try to match each url to the file within `pages` module, but this can be overrided. For more information, see
[Routing in Frontik applications](/docs/routing.md)).
