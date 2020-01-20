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

Application initialization is done in 2 steps:

```
from frontik.app import FrontikApplication


class MyApplication(FrontikApplication):
    def __init__(self, **settings):
        super().__init__(**settings)

        self.cache = self.populate_shared_cache()

    def init_async(self):
        futures = super().init_async()

        futures.append(self.connect_to_database())

        return futures
```

At first, application instance is created by calling __init__ function. In case of multi-worker setup
(see [Configuring Frontik (workers)](/docs/config.md)) this is done before calling fork enabling copy-on-write
for read only data in child processes. It comes with a limitation - IOLoop instance must not be used inside this function.
See tornado.tcpserver.TCPServer for details.

After that init_async is called in each worker process. This function returns a list of futures to be awaited
before worker starts accepting requests. Application must call parent's init_async and preserve returned futures.

For this class to be used, you should set app_class option on frontik configuration file to 'MyApplication'

Config parameter from FrontikApplication application_config method is accessible from `PageHandler` instances
via `self.config` attribute.

There are also certain application configs that affects frontik. For the list of such configuration parameters,
see [Configuring Frontik application](/docs/config-app.md).

Frontik application must contain a `pages` module, containing application controllers. By default, routing mechanism
will try to match each url to the file within `pages` module, but this can be overrided. For more information, see
[Routing in Frontik applications](/docs/routing.md)).
