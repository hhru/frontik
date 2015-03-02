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
```

Application root module may contain class with overrides frontik.app.FrontikApplication class, providing application
specific configs and url mappings, for example:

```
from frontik.app import FrontikApplication


class MyApplication(FrontikApplication):
    def application_config(self):
        return config

    def application_urls(self):
        return config.urls
```

For this class to be used, you should set app_class option on frontik configuration file to 'MyApplication'

Config parameter from FrontikApplication application_config method is accessible from `PageHandler` instances
via `self.config` attribute.

There are also certain application configs that affects frontik. For the list of such configuration parameters,
see [Configuring Frontik application](/docs/config-app.md).

Frontik application must contain a `pages` module, containing application controllers. By default, routing mechanism
will try to match each url to the file within `pages` module, but this can be overrided. For more information, see
[Routing in Frontik applications](/docs/routing.md)).
