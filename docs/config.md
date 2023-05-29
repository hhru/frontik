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
| `app`                        | `str`   | `None`        | Application name  (is used for application identification and as default path to it's class)|
| `app_class`                  | `str`   | `None`        | Path to application class (by default `FrontikApplication` class is used (see [Frontik application structure](/docs/frontik-app.md))) |
| `workers`                    | `int`   | `1`           | Number of worker processes creates using fork. When default value is used, master itself become worker, without fork |
| `init_workers_timeout_sec`   | `int`   | `60`          | Timeout for worker initialization                                      |
| `xheaders  `                 | `bool`  | `False`       | Controls Tornado HTTPServer `xheaders` option                          |
| `tornado_settings`           | `dict`  | `None`        | tornado.web.Application settings                                       |
| `autoreload`                 | `bool`  | `False`       | Restart Frontik after changes in application sources or config files   |
| `debug`                      | `bool`  | `False`       | Enable debug mode                                                      |
| `debug_login`                | `str`   | `None`        | Debug mode login for basic authentication (when `debug=False`)         |
| `debug_password`             | `str`   | `None`        | Debug mode password for basic authentication (when `debug=False`)      |
| `max_active_handlers`        | `int`   | `100`         | Limit the maximum number of simultaneous requests per worker           |
| `datacenter`                 | `str`   | `None`        | Datacenter where current application is running                        |
| `validate_request_id`        | `bool`  | `False`       | Enable check for validity of request_id (32 characters hex-string)     |
| `node_name`                  | `str`   | `False`       | Name of node where frontik application starts                          |
| `common_executor_pool_size`  | `int`   | `10`          | The maximum number of threads that can be used to execute the given calls |
| `stop_timeout`               | `int`   | `3`           | Max time in seconds for gracefully application stopping                |

Logging options:

| Option name                                 | Type    | Default value | Description                                                            |
|---------------------------------------------|---------|---------------|------------------------------------------------------------------------|
| `log_level`                                 | `str`   | `info`        | Python log level                                                       |
| `logformat`                                 | `str`   | see code      | Log entry format for files and syslog                                  |
| `log_dir`                                   | `str`   | `None`        | Log directory location (set to `None` to disable logging to file)      |
| `log_json`                                  | `bool`  | `True`        | Enable JSON logging for files and syslog                               |
| `log_text_format`                           | `str`   | see code      | Log format for files and syslog when JSON logging is disabled          |
| `stderr_log`                                | `bool`  | `False`       | Send log output to stderr (colorized if possible)                      |
| `stderr_format`                             | `str`   | see code      | Log entry format for stderr output                                     |
| `stderr_dateformat`                         | `str`   | see code      | Log entry date format for stderr output                                |
| `syslog`                                    | `bool`  | `False`       | Enables sending logs to syslog                                         |
| `syslog_host`                               | `str`   | `127.0.0.1`   | Syslog host                                                            |
| `syslog_port`                               | `int`   | `None`        | Syslog port. If this value is None, unix socket is used, UDP otherwise |
| `syslog_facility`                           | `str`   | `'user'`      | Syslog facility                                                        |
| `syslog_tag`                                | `str`   | `''`          | Syslog tag                                                             |
| `suppressed_loggers`                        | `list`  | `[]`          | List of logger names to be excluded from debug output                  |
| `sentry_dsn`                                | `str`   | `None`        | Enable Sentry and set Sentry DSN for sending errors                    |
| `statsd_host`                               | `str`   | `None`        | Stats server host for metrics                                          |
| `statsd_port`                               | `int`   | `None`        | Stats server port for metrics                                          |
| `statsd_default_periodic_send_interval_sec` | `int`   | `60`          | Stats default periodic metrics sending interval                        |
| `asyncio_task_threshold_sec`                | `float` | `None`        | Threshold for logging long-running asyncio tasks                       |
| `asyncio_task_critical_threshold_sec`       | `float` | `None`        | Threshold for send to Sentry long-running asyncio tasks                |

HTTP client options:

| Option name                                   | Type    | Default value      | Description                                                                                |
| --------------------------------------------- | ------- | ------------------ | ------------------------------------------------------------------------------------------ |
| `max_http_clients`                            | `int`   | `100`              | Curl max clients option                                                                    |
| `max_http_clients_connects`                   | `int`   | `None`             | Curl max connects option                                                                   |
| `http_client_default_connect_timeout_sec`     | `float` | `0.2`              | Default connect timeout                                                                    |
| `http_client_default_request_timeout_sec`     | `float` | `2.0`              | Default request timeout                                                                    |
| `http_client_default_max_tries`               | `int`   | `2`                | Maximum number of retries per request + 1                                                  |
| `http_client_default_max_timeout_tries`       | `int`   | `1`                | Maximum number of retries due to timeout per request + 1                                   |
| `http_client_default_retry_policy`            | `dict`  | `{599: False, 503: False}` | Conditions when request retry is possible                                                  |
| `http_proxy_host`                             | `str`   | `None`             | HTTP proxy host for Curl HTTP client                                                       |
| `http_proxy_port`                             | `int`   | `3128`             | HTTP proxy port for Curl HTTP client                                                       |
| `http_client_allow_cross_datacenter_requests` | `bool`  | `False`            | Allow requests to different datacenter when no upstream in current datacenter is available |
| `timeout_multiplier`                          | `float` | `1.0`              | Generic timeout multiplier for http requests (useful for testing)                          |

Producers options:

| Option name                         | Type   | Default value | Description                                           |
|-------------------------------------|--------|---------------|-------------------------------------------------------|
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

Consul options:

| Option name                                 | Type   | Default value | Description                                                            |
|---------------------------------------------|--------|---------------|------------------------------------------------------------------------|
| `consul_enabled`                            | `bool` | `True`        | Enable Consul features: registration, kv-store, upstreams              |
| `consul_host`                               | `str`  | `127.0.0.1`   | Consul host                                                            |
| `consul_port`                               | `int`  | `None`        | Consul port                                                            |    
| `consul_service_address`                    | `str`  | `None`        | Address of application for Consul registration                         |
| `consul_check_host`                         | `str`  | `None`        | Address for healthcheck application, if not provided, `consul_service_address` is used  |
| `consul_http_check_interval_sec`            | `int`  | `10`          | Interval for making healthcheck request                                |
| `consul_http_check_timeout_sec`             | `int`  | `1`           | Timeout for health check request                                       |
| `consul_tags`                               | `list` | `[]`          | Additional parameters, which will will be sent with Consul registration     |
| `consul_weight_watch_seconds`               | `int`  | `600`         | Max waiting blocking query time for get host weight from Consul        |
| `consul_weight_total_timeout_sec`           | `int`  | `650`         | Timeout for waiting blocking query for getting host weight from Consul |
| `consul_cache_initial_warmup_timeout_sec`   | `int`  | `2`           | Ttl of HTTP session to initialize cache                                |
| `consul_cache_backoff_delay_seconds`        | `int`  | `10`          | Interval to wait until next attempt to fetch info from consul after exception   |
| `consul_consistency_mode`                   | `str`  | `default`     | May set as `default`, `consistent` and `stale`. See Consul documentation   |
| `consul_weight_consistency_mode`            | `str`  | `default`     | Consistency mode for get weigth.                                       |
| `consul_deregister_critical_timeout`        | `str`  | `120h`        | Time, after that service will be de-registered automatically from Consul |
| `upstreams`                                 | `list` | `[]`          | List of service upstreams - services, where current app will send http requests |
| `fail_start_on_empty_upstream`              | `bool` | `True`        | If `True` app will not start if one or more upstreams don't have host addresses |

Opentelemetry options:

| Option name                         | Type   | Default value | Description                                                            |
|-------------------------------------|--------|---------------|------------------------------------------------------------------------|
| `opentelemetry_collector_url`       | `str`  | `127.0.0.1`   | OpenTelemetry collector url                                            |
| `opentelemetry_sampler_ratio`       | `float`| `0.01`        | Probability (between 0 and 1) that a span will be sampled              |
| `opentelemetry_enabled`             | `bool` | `False`       | Enable OpenTelemetry features                                          |

The only option that is mandatory for running Frontik is `app` option — the name of application package.

There are also certain options, that can be defined during application initialization, see
[Configuring Frontik application](/docs/config-app.md) for more details.
