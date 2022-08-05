import logging
import sys
from dataclasses import asdict

import tornado.autoreload
from http_client.options import parse_config_file as http_client_parse_config_file

from frontik.loggers import bootstrap_core_logging, MDC
from frontik.options import options, parse_config_file

log = logging.getLogger('server')


def parse_configs(config_files):
    """Reads command line options / config file and bootstraps logging.
    """
    parse_command_line()

    if options.config:
        configs_to_read = options.config
    else:
        configs_to_read = config_files

    configs_to_read = filter(
        None, [configs_to_read] if not isinstance(configs_to_read, (list, tuple)) else configs_to_read
    )

    for config in configs_to_read:
        http_client_parse_config_file(config)
        parse_config_file(config)

    # override options from config with command line options
    parse_command_line()
    MDC.init('master')
    bootstrap_core_logging()
    for config in configs_to_read:
        log.debug('using config: %s', config)
        if options.autoreload:
            tornado.autoreload.watch(config)


def parse_command_line():
    args = sys.argv

    for i in range(1, len(args)):
        if not args[i].startswith("-"):
            break
        if args[i] == "--":
            break
        arg = args[i].lstrip("-")
        name, equals, value = arg.partition("=")
        if name not in asdict(options).keys():
            raise Exception('Unrecognized command line option: %r' % name)
        if not equals:
            if type(getattr(options, name)) == bool:
                setattr(options, name, True)
            else:
                raise Exception('Option %r requires a value' % name)

        if type(getattr(options, name)) == int and isinstance(value, str):
            value = int(value)
        setattr(options, name, value)
