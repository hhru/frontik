import logging
import sys
from dataclasses import asdict, fields

import tornado.autoreload
from http_client.options import parse_config_file as http_client_parse_config_file, options as http_client_options

from frontik.loggers import bootstrap_core_logging, MDC
from frontik.options import options, parse_config_file

log = logging.getLogger('config_parser')


def parse_configs(config_files):
    """Reads command line options / config file and bootstraps logging.
    """
    allowed_options = {**asdict(options), **asdict(http_client_options)}.keys()
    parse_command_line(options, allowed_options)

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
    parse_command_line(options, allowed_options)
    parse_command_line(http_client_options, allowed_options)
    MDC.init('master')
    bootstrap_core_logging()
    for config in configs_to_read:
        log.debug('using config: %s', config)
        if options.autoreload:
            tornado.autoreload.watch(config)


def parse_command_line(options, allowed_options):
    args = sys.argv

    for i in range(1, len(args)):
        if not args[i].startswith("-"):
            break
        if args[i] == "--":
            break
        arg = args[i].lstrip("-")
        name, equals, value = arg.partition("=")
        if name not in allowed_options:
            raise Exception('Unrecognized command line option: %r' % name)

        option = next(filter(lambda x: x.name == name, fields(options)), None)
        if option is None:
            continue

        if not equals:
            if option.type == bool:
                setattr(options, name, True)
            else:
                raise Exception('Option %r requires a value' % name)

        if option.type == bool:
            setattr(options, name, value.lower() not in ("false", "0", "f"))
        elif option.type == int:
            setattr(options, name, int(value))
        elif option.type == float:
            setattr(options, name, float(value))
        elif option.type == str:
            setattr(options, name, value)
        else:
            raise Exception('Complex types are not implemented %r: %r' % (name, value))
