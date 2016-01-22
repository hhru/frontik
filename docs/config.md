## Configuring Frontik

Here is the list of all options currently supported by Frontik.
All of them can be set in the configuration file (see [frontik_dev.cfg.ex](/frontik_dev.cfg.ex) for example),
but you can pass them to `/usr/bin/frontik` script through command line as well. The exception is `config` option — it makes sense to pass it only through command line.

These options can be set for each Frontik instance (see [options.py](/frontik/options.py)).

| Option name                  | Type    | Default value | Description                                                            |
| ---------------------------- | ------- | ------------  | ---------------------------------------------------------------------- |
| `host`                       | `str`   | `'0.0.0.0'`   | Host value for incoming connections                                    |
| `port`                       | `int`   | `8000`        | Port to listen to                                                      |
| `config`                     | `str`   | `None`        | Path to config file                                                    |
| `daemonize`                  | `bool`  | `False`       | Start Frontik instance     as daemon                                   |
| `pidfile`                    | `str`   | `None`        | Pidfile location (if `None`, pidfile won't be created)                 |
| `log_blocked_ioloop_timeout` | `float` | `0`           | Enables logging of long-running IOLoop iterations                      |
| `app`                        | `str`   | `None`        | Application package name (see [Frontik application structure](/docs/frontik-app.md)) |
| `app_class`                  | `str`   | `None`        | Application class name defined in application root module (by default `FrontikApplication` class is used) |
| `app_root_url`               | `str`   | `''`          | <a name="app_root_url"></a>Root url for the application                |
| `tornado_settings`           | `dict`  | `None`        | tornado.web.Application settings                                       |
| `autoreload`                 | `bool`  | `True`        | Restart Frontik after changes in application sources or config files   |
| `debug`                      | `bool`  | `False`       | Enable debug mode                                                      |
| `debug_login`                | `str`   | `None`        | Debug mode login for basic authentication (when `debug=False`)         |
| `debug_password`             | `str`   | `None`        | Debug mode password for basic authentication (when `debug=False`)      |
| `xsl_executor`               | `str`   | `'threaded'`  | Executor type for XSL templating (alternative: `'ioloop'`)             |
| `json_executor`              | `str`   | `'ioloop'`    | Executor type for JSON templating                                      |
| `warn_no_jobs`               | `bool`  | `True`        | Write a warning if no jobs were found in executor queue                |
| `timeout_multiplier`         | `float` | `1.0`         | Generic timeout multiplier for get_xxx calls (useful for testing)      |
| `handlers_count`             | `int`   | `100`         | Limit for number of simultaneous requests handled by Frontik instance  |
| `http_proxy_host`            | `str`   | `None`        | HTTP proxy host for Curl HTTP client                                   |
| `http_proxy_port`            | `int`   | `3128`        | HTTP proxy port for Curl HTTP client                                   |

Logging options:

| Option name                  | Type    | Default value | Description                                                            |
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

The only option that is mandatory for running Frontik is `app` option — the name of application package.

If you are using the [built-in supervisor](/docs/supervisor.md), you should specify the options for starting several
Frontik instances in the same configuration file

There are also certain options, that can be defined during application initialization, see
[Configuring Frontik application](/docs/config-app.md) for more details.
