## Debug mode

Frontik supports extended debug mode. It is enabled by query or form parameter 'debug'
(you can also set cookie `debug=...`).

Available options are:

* `debug=true` (or just `debug`) — simple debug
* `debug=full` — extended debug
* `debug=nopass` — disables passing debug header to services
* `debug=xslt` — enables XSL transformation profiling
* `debug=@text` — highlights log entries matching 'text'

You can combine these options, for example: `debug=full,nopass`

By default, in debug mode Frontik adds HTTP header `X-Hh-Debug` to all requests. Some services may in return form a
debug response, containing debug log in XML format together with serialized original response. Debug responses should
be returned with X-Hh-Debug header as well. This behaviour can be disabled with `debug=nopass`.

As well as `debug` parameter, there are also parameters, that can disable templating:

* `notpl` — disables templating (XSLT or Jinja2)
* `noxsl` — old synonym, that works only for XSLT
