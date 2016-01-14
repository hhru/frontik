## Using built-in supervisor

A supervisor from [frontik.server.supervisor](/frontik/server/supervisor.py) module can be used to run and control
Frontik instances in production.

An example of supervisor usage can be found in Frontik test suite — [supervisor-testapp](/supervisor-testapp).

It contains few simple statements:

```python
from frontik.server.supervisor import supervisor

supervisor(
    script='./frontik-test',
    app='tests.projects.test_app',
    config='tests/projects/frontik_debug.cfg'
)
```

`supervisor` function accepts three parameters:

* `script` is a path to a script, which is used to start Frontik instance. If Frontik is installed as a package,
it provides such script in [/usr/bin/frontik](/scripts/frontik)
* `config` is a path to configuration file (see [Configuring Frontik](/docs/config.md))
* `app` is an optional parameter defining the application package name (if it is not set, the value from configuration file is used)

Supervisor script can be used as an ordinary init.d-script and supports `start`, `stop`, `restart` and `status` control commands.

For example:

```console
supervisor-testapp restart

[13:07:58 root] some of the workers are running, trying to kill
[13:07:58 root] stopping worker 1500
[13:07:58 root] stopping worker 1501
[13:07:59 root] stopping worker 1502
[13:08:04 root] start worker 1500
[13:08:04 root] start worker 1501
[13:08:04 root] start worker 1502
[13:08:05 root] waiting for worker on port 1500 to start
[13:08:05 root] waiting for worker on port 1501 to start
[13:08:05 root] waiting for worker on port 1502 to start
[13:08:06 root] all workers are running
```

### Configuring supervisor

The following options can be set for Frontik supervisor.

| Option name                  | Type   | Default value   | Description                        |
| ---------------------------- | ------ | --------------- | ---------------------------------- |
| `workers_count`              | `int`  | `4`             | Number of Frontik instances to run |
| `start_port`                 | `int`  | `8000`          | First port number to bind to       |
| `pidfile_template`           | `str`  | `None`          | Pidfile template, containing `%(port)s` placeholder |
| `logfile_template`           | `str`  | `None`          | Logfile template, containing `%(port)s` placeholder |
| `supervisor_sigterm_timeout` | `int`  | `4`             | Time in seconds to wait before sending SIGKILL (after SIGTERM has been sent) |
| `nofile_soft_limit`          | `int`  | `4096`          | The value of soft NOFILE limit     |

Supervisor starts `workers_count` separate processes using the `script` executable (which is passed to `supervisor` function).
It starts the instances using consecutive port numbers (`start_port`, `start_port + 1` ... `start_port + workers_count - 1`).
Port number is passed to the `script` executable through command line `--port` argument.
`--pidfile` and `--logfile` command line arguments are constructed from `pidfile_template` and `logfile_template`
by replacing `%(port)s` placeholder with a port number of an instance.
