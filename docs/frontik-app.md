## Frontik application structure

The list of Frontik applications is defined in Frontik configuration file (see [Configuring Frontik](/docs/config.md)).
Here is an example:

```python
from frontik.app import App

urls = [
    (r'/page[0-9]', App('app1', '../some/relative/path')),
    (r'/test_app', App('app2', '/absolute/path/to/application')),
]
```

`urls` option is a list of tuples, which describe each application. The first item in a tuple is
a regular expression, matching the beginning of urls, which should map to the application. The second item is a
`frontik.app.App` instance, initialized with the name of the application and its root path (absolute or relative to
the location of runner script).

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

Frontik application must contain a (possibly empty) `config.py` file. It will be executed once at the start of
Frontik server and can contain custom application initialization code.

There are certain global values that you can set in `config.py`. Frontik will recognize them and behave accordingly.
For the list of such configuration parameters, see [Configuring Frontik application](/docs/config-app.md).

Frontik application must also contain a `pages` module, containing controllers files. By default, routing mechanism
will try to match each url to the file within `pages` module, but this can be overrided. For more information, see
[Routing in Frontik applications](/docs/routing.md)).
