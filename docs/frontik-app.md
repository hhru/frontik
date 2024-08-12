## Frontik application structure

Each Frontik instance serves one application, which is imported from a package specified in
`app_class` parameter (see [Running Frontik](/docs/running.md)).

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
specific configs, for example:

```
from frontik.app import FrontikApplication


class MyApplication(FrontikApplication):
    def application_config(self):
        return config
```

Application initialization is done in 2 steps:

```
from frontik.app import FrontikApplication


class MyApplication(FrontikApplication):
    def __init__(self, **settings):
        super().__init__(**settings)

        self.cache = self.populate_shared_cache()

    async def init(self):
        await super().init()

        await self.connect_to_database()
```

At first, application instance is created by calling __init__ function. In case of multi-worker setup
(see [Configuring Frontik (workers)](/docs/config.md)) this is done before calling fork enabling copy-on-write
for read only data in child processes. It comes with a limitation - IOLoop instance must not be used inside this function.
See tornado.tcpserver.TCPServer for details.

After that init is being called in each worker process.

For this class to be used, you should set app_class option on frontik configuration file to 'MyApplication'

Config parameter from FrontikApplication application_config method is accessible from `PageHandler` instances
via `self.config` attribute.

There are also certain application configs that affects frontik. For the list of such configuration parameters,
see [Configuring Frontik application](/docs/config-app.md).

Frontik application must contain a `pages` module, containing application controllers. By default, routing mechanism
will try to match each url to the file within `pages` module, but this can be overrided. For more information, see
[Routing in Frontik applications](/docs/routing.md)).
