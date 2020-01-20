## Configuring Frontik

Here is the list of all options currently supported by Frontik.
All of them can be set in the configuration file (see [frontik_dev.cfg.ex](/frontik_dev.cfg.ex) for example),
but you can pass them to `/usr/bin/frontik` script through command line as well. The exception is `config` option — it makes sense to pass it only through command line.

These options can be set for each Frontik instance (see [options.py](/frontik/options.py)).

| Option name                  | Type    | Default value | Description                                                            |
| ---------------------------- | ------- | ------------  | ---------------------------------------------------------------------- |
| `host`                       | `str`   | `'0.0.0.0'`   | Host value for incoming connections                                    |
| `port`                       | `int`   | `8000`        | Port to listen to                                                      |
| `reuse_port`                 | `bool`  | `True`        | Binds server socket with SO_REUSEPORT option                           |
| `config`                     | `str`   | `None`        | Path to config file                                                    |
| `slow_callback_threshold_ms` | `int`   | `None`        | Enables logging of long-running callbacks                              |
| `app`                        | `str`   | `None`        | Application package name (see [Frontik application structure](/docs/frontik-app.md)) |
| `app_class`                  | `str`   | `None`        | Application class name defined in application root module (by default `FrontikApplication` class is used) |
| `workers`                    | `int`   | `1`           | Number of worker processes creates using fork. When default value is used, master itself become worker, without fork |
| `xheaders  `                 | `bool`  | `False`       | Controls Tornado HTTPServer `xheaders` option                          |
| `tornado_settings`           | `dict`  | `None`        | tornado.web.Application settings                                       |
| `autoreload`                 | `bool`  | `False`       | Restart Frontik after changes in application sources or config files   |
| `debug`                      | `bool`  | `False`       | Enable debug mode                                                      |
| `debug_login`                | `str`   | `None`        | Debug mode login for basic authentication (when `debug=False`)         |
| `debug_password`             | `str`   | `None`        | Debug mode password for basic authentication (when `debug=False`)      |
| `handlers_count`             | `int`   | `100`         | Limit for number of simultaneous requests handled by Frontik instance  |
| `datacenter`                 | `str`   | `None`        | Datacenter where current application is running                        |

Logging options:

| Option name                  | Type    | Default value | Description                                                            |
|------------------------------|---------|---------------|------------------------------------------------------------------------|
| `loglevel`                   | `str`   | `info`        | Python log level                                                       |
| `logformat`                  | `str`   | see code      | Log entry format for files and syslog                                  |
| `logfile`                    | `str`   | `None`        | Log file location (set to `None` to disable logging to file)           |
| `stderr_log`                 | `bool`  | `False`       | Send log output to stderr (colorized if possible)                      |
| `stderr_format`              | `str`   | see code      | Log entry format for stderr output                                     |
| `stderr_dateformat`          | `str`   | see code      | Log entry date format for stderr output                                |
| `syslog`                     | `bool`  | `False`       | Enables sending logs to syslog                                         |
| `syslog_address`             | `str`   | `'/dev/log'`  | Syslog address, unix socket name or server address                     |
| `syslog_port`                | `int`   | `None`        | Syslog port. If this value is None, unix socket is used, UDP otherwise |
| `syslog_facility`            | `str`   | `'user'`      | Syslog facility                                                        |
| `suppressed_loggers`         | `list`  | `[]`          | List of logger names to be excluded from debug output                  |
| `sentry_dsn`                 | `str`   | `None`        | Enable Sentry and set Sentry DSN for sending errors                    |
| `statsd_host`                | `str`   | `None`        | Stats server host for metrics                                          |
| `statsd_port`                | `int`   | `None`        | Stats server port for metrics                                          |
| `asyncio_task_threshold_sec` | `int`   | `None`        | Threshold for logging long-running asyncio tasks                       |

HTTP client options:

| Option name                                   | Type    | Default value      | Description                                                                                |
| --------------------------------------------- | ------- | ------------------ | ------------------------------------------------------------------------------------------ |
| `max_http_clients`                            | `int`   | `100`              | Curl max clients option                                                                    |
| `max_http_clients_connects`                   | `int`   | `None`             | Curl max connects option                                                                   |
| `http_client_default_connect_timeout_sec`     | `float` | `0.2`              | Default connect timeout                                                                    |
| `http_client_default_request_timeout_sec`     | `float` | `2.0`              | Default request timeout                                                                    |
| `http_client_default_max_tries`               | `int`   | `2`                | Maximum number of retries per request + 1                                                  |
| `http_client_default_max_timeout_tries`       | `int`   | `1`                | Maximum number of retries due to timeout per request + 1                                   |
| `http_client_default_max_fails`               | `int`   | `0`                | Number of consecutive fails before server is considered dead                               |
| `http_client_default_fail_timeout_sec`        | `float` | `10`               | Timeout before starting making requests to a dead server                                   |
| `http_client_default_retry_policy`            | `str`   | `timeout,http_503` | Conditions when request retry is possible                                                  |
| `http_proxy_host`                             | `str`   | `None`             | HTTP proxy host for Curl HTTP client                                                       |
| `http_proxy_port`                             | `int`   | `3128`             | HTTP proxy port for Curl HTTP client                                                       |
| `http_client_allow_cross_datacenter_requests` | `bool`  | `False`            | Allow requests to different datacenter when no upstream in current datacenter is available |
| `timeout_multiplier`                          | `float` | `1.0`              | Generic timeout multiplier for http requests (useful for testing)                          |

Producers options:

| Option name                         | Type   | Default value | Description                                           |
| `xsl_root`                          | `str`  | `None`        | Root directory for XSL files                          |
| `xml_root`                          | `str`  | `None`        | Root directory for XML files                          |
| `xsl_cache_limit`                   | `int`  | `None`        | Upper limit for XSL LRU files cache                   |
| `xml_cache_limit`                   | `int`  | `None`        | Upper limit for XML LRU files cache                   |
| `xsl_cache_step`                    | `int`  | `None`        | Increase in weight for XSL cache entry after each get |
| `xml_cache_step`                    | `int`  | `None`        | Increase in weight for XML cache entry after each get |
| `xsl_executor_pool_size`            | `int`  | `1`           | Number of background threads for XSLT processing      |
| `jinja_template_root`               | `str`  | `None`        | Root directory for Jinja templates                    |
| `jinja_template_cache_limit`        | `int`  | `50`          | Upper limit for Jinja templates cache                 |
| `jinja_streaming_render_timeout_ms` | `int`  | `50`          | Upper limit (in msecs) for one iteration of partial Jinja template rendering |

The only option that is mandatory for running Frontik is `app` option — the name of application package.

There are also certain options, that can be defined during application initialization, see
[Configuring Frontik application](/docs/config-app.md) for more details.
