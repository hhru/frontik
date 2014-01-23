## Configuring Frontik

Here is the list of all options, currently supported by Frontik.
All of them are set in config file (see [frontik_dev.cfg.ex](/frontik_dev.cfg.ex) for example),
but you can pass them through command line as well. The exception is `config` option — it makes no sense for it to be set in config file.

These options are defined in [tornado.server](https://github.com/hhru/tornado/blob/master/tornado/server/__init__.py) module
and are essential for running Frontik server and logging in Frontik applications.

| Option name        | Type   | Default value   | Description                                              |
| ------------------ | ------ | --------------- | -------------------------------------------------------- |
| `host`             | `str`  | `'0.0.0.0'`     | Host value for incoming connections                      |
| `port`             | `int`  | `8000`          | Port to listen to                                        |
| `config`           | `str`  | `None`          | Path to config file                                      |
| `daemonize`        | `bool` | `False`         | Start Frontik as daemon                                  |
| `pidfile`          | `str`  | `None`          | Pidfile location (if `None`, pidfile won't be created)   |
| `logfile`          | `str`  | `None`          | Logfile location (if `None`, Frontik will log to stderr) |
| `loglevel`         | `str`  | `info`          | The lowest log level written to logfile                  |
| `logformat`        | `str`  | see code        | Log entry format                                         |

The following options are specific to [tornado.server.supervisor](https://github.com/hhru/tornado/blob/master/tornado/server/supervisor.py)
module, which provides convenient interface for running and controlling several Frontik instances on one machine.

| Option name        | Type   | Default value   | Description                                              |
| ------------------ | ------ | --------------- | -------------------------------------------------------- |
| `workers_count`    | `int`  | `4`             | Number of Frontik instances to run (on ports `port`, `port + 1` ... `port + N`) |
| `pidfile_template` | `str`  | `None`          | Pidfile template, containing `%(port)s` placeholder (passed as `--pidfile` option to separate Frontik instances) |
| `logfile_template` | `str`  | `None`          | Logfile template, containing `%(port)s` placeholder (passed as `--logfile` option to separate Frontik instances) |

These options are defined in Frontik (see [options.py](/frontik/options.py)) and are common to all Frontik applications,
which run on one Frontik instance.

| Option name          | Type    | Default value | Description                                                           |
| -------------------- | ------- | ------------  | --------------------------------------------------------------------- |
| `autoreload`         | `bool`  | `True`        | Restart Frontik after changes in application sources or config files  |
| `debug`              | `bool`  | `False`       | Enable debug mode by default (will show debug output on every error)  |
| `debug_login`        | `str`   | `None`        | Debug mode login for basic authentication                             |
| `debug_password`     | `str`   | `None`        | Debug mode password for basic authentication                          |
| `debug_xsl`          | `str`   | see code      | Debug page XSL template                                               |
| `suppressed_loggers` | `list`  | `[]`          | List of logger names to be excluded from debug output                 |
| `syslog`             | `bool`  | `False`       | Enables sending logs to syslog                                        |
| `syslog_address`     | `str`   | `'/dev/log'`  | Syslog address                                                        |
| `syslog_facility`    | `str`   | `'user'`      | Syslog facility                                                       |
| `syslog_msg_max_length` | `int` | `2048`       | Syslog max message length                                             |
| `graylog`            | `bool`  | `False`       | Enables sending logs to Graylog                                       |
| `graylog_host`       | `str`   | `'localhost'` | Graylog host                                                          |
| `graylog_port`       | `int`   | `12201`       | Graylog port                                                          |
| `xsl_executor`       | `str`   | `'threaded'`  | Executor type for XSL templating (alternative: `'ioloop'`)            |
| `json_executor`      | `str`   | `'ioloop'`    | Executor type for JSON templating                                     |
| `warn_no_jobs`       | `bool`  | `True`        | Write a warning if no jobs were found in executor queue               |
| `timeout_multiplier` | `float` | `1.0`         | Generic timeout multiplier for get_xxx calls (useful for testing)     |
| `handlers_count`     | `int`   | `100`         | Limit for number of simultaneous requests handled by Frontik instance |
| `urls`               | `list`  | `[]`          | List of Frontik applications (see [Frontik application structure](/docs/frontik-app.md)) |

There are also certain options, that are unique for each application, see
[Configuring Frontik application](/docs/config-app.md) for more details.
