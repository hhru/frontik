## Service urls

There are some service urls available for an any frontik app.
[`app_root_url` option](config.md#app_root_url) doesn't affect them, they are always served from `/`.

* `/status` – returns `200 OK` if the server is ready to process requests, an error otherwise.
  Response contains json with information about the server and some useful counters:
```json
{
    "uptime": "99.28 hours and 16.53 minutes"
}
```
* `/version` – xml with app version and versions of some dependencies
