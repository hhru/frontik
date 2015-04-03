## Service urls

There are some service urls those available for an any frontik app.
[`app_root_url` option](config.md#app_root_url) not affects them, they always served from `/`.

* `/status?no_network_check=true` - returns `200 OK` if the server is ready to process requests, other errors otherwise.
  Response contains json with information about the server with a some useful counters:
```json
{
    "uptime": "99.28 hours and 16.53 minutes",
    "pages served": 2386542,
    "bytes from http requests": 25379492996,
    "http requests made": 5811649
}
```
* `/status` - the same as `/status?no_network_check=true`, but also with additional http request to the server itself.
* `/version` - xml with app version and versions of some dependencies
* `/types_count` - returns a list with amount of object types tracked by the garbage collector
* `/pdb` - opens pdb debbiging session
