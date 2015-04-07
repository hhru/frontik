## Service urls

There are some service urls available for an any frontik app.
[`app_root_url` option](config.md#app_root_url) doesn't affect them, they are always served from `/`.

* `/status?no_network_check=true` – returns `200 OK` if the server is ready to process requests, an error otherwise.
  Response contains json with information about the server and some useful counters:
```json
{
    "uptime": "99.28 hours and 16.53 minutes",
    "pages served": 2386542,
    "bytes from http requests": 25379492996,
    "http requests made": 5811649
}
```
* `/status` – the same as `/status?no_network_check=true`, but with additional http request to the server itself for
  checking client availability.
* `/version` – xml with app version and versions of some dependencies
* `/types_count` – returns a list with amount of object types tracked by the garbage collector
* `/pdb` – opens pdb debugging session
