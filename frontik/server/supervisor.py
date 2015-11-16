#!/usr/bin/python
# coding=utf-8

"""
This is module for creating of init.d scripts for tornado-based
services
It implements following commands:
  * start
  * stop
  * restart
  * status

Sample usage:

#!/usr/bin/python
# coding=utf-8

from frontik.server.supervisor import supervisor

supervisor(
    script='/usr/bin/frontik',
    app='application_package',
    config='/etc/application/frontik.cfg'
)

All exit codes returned by commands are trying to be compatible with LSB standard [1] as much as possible
[1] http://refspecs.linuxbase.org/LSB_3.1.1/LSB-Core-generic/LSB-Core-generic/iniscrptact.html
"""

import signal
import sys
import urllib2
import logging
import subprocess
import time
import glob
import re
import socket
import os
import resource
from functools import partial

from tornado.log import LogFormatter
import tornado.options
from tornado.options import options

tornado.options.define('start_port', 8000, int)
tornado.options.define('workers_count', 4, int)
tornado.options.define('logfile_template', None, str)
tornado.options.define('pidfile_template', None, str)
tornado.options.define('supervisor_sigterm_timeout', 4, int)
tornado.options.define('nofile_soft_limit', 4096, int)
tornado.options.define('with_coverage', False, bool)

STARTER_SCRIPTS = {}


def worker_is_alive(port, config):
    try:
        path_beginning, _, path_ending = options.pidfile_template.partition('%(port)s')
        pidfile_regex = '{0}([0-9]+){1}'.format(re.escape(path_beginning), re.escape(path_ending))
        for pid in subprocess.check_output('pgrep -f "{}"'.format(pidfile_regex), shell=True).strip().split('\n'):
            with open('/proc/{}/cmdline'.format(pid.strip()), 'r') as cmdline_file:
                cmdline = cmdline_file.readline()
                if cmdline is not None and str(port) in cmdline and config in cmdline and 'python' in cmdline:
                    return True
        return False
    except (IOError, subprocess.CalledProcessError):
        return False


def worker_is_running(port):
    try:
        response = urllib2.urlopen('http://localhost:{}/status/'.format(port), timeout=1)
        for (header, value) in response.info().items():
            if header == 'server' and value.startswith('TornadoServer'):
                return True
        return False
    except urllib2.URLError:
        return False
    except socket.error as e:
        logging.warn('socket error ({}) on port {}'.format(e, port))
        return False


def worker_is_started(port, config):
    shell_script_exited = STARTER_SCRIPTS.get(port, None) is None or STARTER_SCRIPTS[port].poll() is not None
    if not shell_script_exited:
        return False

    alive = worker_is_alive(port, config)
    running = worker_is_running(port)

    if alive and running:
        return True

    if not alive and not running:
        logging.error('worker on port %s failed to start', port)
        return True

    logging.info('waiting for worker on port %s to start', port)
    return False


def start_worker(script, config=None, port=None, app=None):
    if worker_is_alive(port, config):
        logging.warn('another worker already started on %s', port)
        return None

    logging.debug('start worker %s', port)

    args = script.split() + [
        '--config={}'.format(config),
        '--port={}'.format(port),
        '--pidfile={}'.format(options.pidfile_template % dict(port=port))
    ]

    if app is not None:
        args.append('--app={}'.format(app))

    if options.logfile_template:
        args.append('--logfile={}'.format(options.logfile_template % dict(port=port)))

    if options.with_coverage:
        args = ['coverage', 'run'] + args

    STARTER_SCRIPTS[port] = subprocess.Popen(args)
    return STARTER_SCRIPTS[port]


def stop_worker(port, signal_to_send=signal.SIGTERM):
    logging.debug('stopping worker %s', port)
    path = options.pidfile_template % dict(port=port)
    if not os.path.exists(path):
        logging.warning("pidfile %s does not exist, don't know how to stop", path)
    try:
        pid = int(file(path).read())
        os.kill(pid, signal_to_send)
    except (OSError, IOError, ValueError):
        pass


def cleanup_worker(port):
    pid_path = options.pidfile_template % dict(port=port)
    if os.path.exists(pid_path):
        try:
            os.remove(pid_path)
        except Exception as e:
            logging.warning('failed to remove %s (%s)', pid_path, e)


def map_workers(f):
    return map(f, [options.start_port + p for p in range(options.workers_count)])


def map_stale_workers(f):
    ports = [str(options.start_port + p) for p in range(options.workers_count)]
    stale_ports = []

    if options.pidfile_template.find('%(port)s') > -1:
        parts = options.pidfile_template.partition('%(port)s')
        re_escaped_template = ''.join([re.escape(parts[0]), '([0-9]+)', re.escape(parts[-1])])
        # extract ports from pid file names and add them to stale_ports if they are not in ports from settings
        for pidfile in glob.glob(options.pidfile_template % dict(port="*")):
            port_match = re.search(re_escaped_template, pidfile)
            if port_match and not port_match.group(1) in ports:
                stale_ports.append(port_match.group(1))

    return map(f, stale_ports)


def map_all_workers(f):
    return map_workers(f) + map_stale_workers(f)


def stop(config):
    if any(map_all_workers(lambda port: worker_is_alive(port, config))):
        logging.warning('some of the workers are running, trying to kill')

    map_all_workers(
        lambda port: stop_worker(port, signal.SIGTERM) if worker_is_alive(port, config) else cleanup_worker(port)
    )

    time.sleep(options.supervisor_sigterm_timeout)

    map_all_workers(
        lambda port: stop_worker(port, signal.SIGKILL) if worker_is_alive(port, config) else cleanup_worker(port)
    )

    time.sleep(0.1 * options.workers_count)

    map_all_workers(
        lambda port: cleanup_worker(port) if not worker_is_alive(port, config)
        else logging.warning('failed to stop worker on port %d', port)
    )

    if any(map_all_workers(lambda port: worker_is_alive(port, config))):
        logging.warning('failed to stop workers')
        sys.exit(1)


def start(script, app, config):
    map_workers(partial(start_worker, script, config, app=app))
    time.sleep(1)
    while not all(map_workers(lambda port: worker_is_started(port, config))):
        time.sleep(1)
    map_workers(lambda port: cleanup_worker(port) if not worker_is_alive(port, config) else 0)


def status(expect=None):
    res = map_stale_workers(worker_is_running)
    if any(res):
        logging.warn('some stale workers are running!')

    res = map_workers(worker_is_running)

    if all(res):
        if expect == 'stopped':
            logging.error('all workers are running')
            return 1
        else:
            logging.info('all workers are running')
            return 0
    elif any(res):
        logging.warn('some workers are running!')
        return 1
    else:
        if expect == 'started':
            logging.error('all workers are stopped')
            return 1
        else:
            logging.info('all workers are stopped')
            return 3


def _setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)

    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(LogFormatter(
        fmt='%(color)s[%(asctime)s %(name)s]%(end_color)s %(message)s', datefmt='%H:%M:%S'
    ))

    root_logger.addHandler(handler)


def supervisor(script, config, app):
    _setup_logging()

    tornado.options.parse_config_file(config, final=False)
    arguments = tornado.options.parse_command_line(final=False)

    if not arguments:
        logging.error('missing action: please use `start`, `stop`, `restart` or `status`')
        sys.exit(1)

    cmd = arguments[0]

    cur_soft_limit, cur_hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
    new_soft_limit = options.nofile_soft_limit
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft_limit, max(new_soft_limit, cur_hard_limit)))
    except ValueError:
        logging.warning(
            "We don't have CAP_SYS_RESOURCE, therefore soft NOFILE limit will be set to %s",
            min(new_soft_limit, cur_hard_limit)
        )
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(new_soft_limit, cur_hard_limit), cur_hard_limit))

    if cmd == 'start':
        start(script, app, config)
        sys.exit(status(expect='started'))

    if cmd == 'restart':
        stop(config)
        start(script, app, config)
        sys.exit(status(expect='started'))

    elif cmd == 'stop':
        stop(config)
        status_code = status(expect='stopped')
        sys.exit(0 if status_code == 3 else 1)

    elif cmd == 'status':
        sys.exit(status())

    else:
        logging.error('incorrect action: please use `start`, `stop`, `restart` or `status`')
        sys.exit(1)
