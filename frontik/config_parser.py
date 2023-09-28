from __future__ import annotations
import logging
import sys
from dataclasses import asdict, fields
from typing import TYPE_CHECKING
from typing import get_args

import tornado.autoreload
from http_client.options import parse_config_file as http_client_parse_config_file, options as http_client_options

from frontik.loggers import bootstrap_core_logging, MDC
from frontik.options import options, parse_config_file

if TYPE_CHECKING:
    from frontik.options import Options
    from typing import Iterable

log = logging.getLogger('config_parser')


def parse_configs(config_files: str|None) -> None:
    """Reads command line options / config file and bootstraps logging."""
    allowed_options = {**asdict(options), **asdict(http_client_options)}.keys()
    parse_command_line(options, allowed_options)

    if options.config:
        configs_to_read = options.config
    else:
        if config_files is None:
            raise Exception('Configs can not be None')
        configs_to_read = config_files

    configs_to_read_filter = filter(
        None, [configs_to_read] if not isinstance(configs_to_read, (list, tuple)) else configs_to_read
    )

    for config in configs_to_read_filter:
        http_client_parse_config_file(config)
        parse_config_file(config)

    # override options from config with command line options
    parse_command_line(options, allowed_options)
    parse_command_line(http_client_options, allowed_options)
    MDC.init('master')
    bootstrap_core_logging(options.log_level, options.log_json, options.suppressed_loggers)
    for config in configs_to_read_filter:
        log.debug('using config: %s', config)
        if options.autoreload:
            tornado.autoreload.watch(config)


def parse_command_line(options: Options, allowed_options: Iterable) -> None:
    args = sys.argv

    for i in range(1, len(args)):
        if not args[i].startswith("-"):
            break
        if args[i] == "--":
            break
        arg = args[i].lstrip("-")
        name, equals, value = arg.partition("=")
        if name not in allowed_options:
            log.error(f'Unrecognized command line option: {name}, skipped')
            continue

        option = next(filter(lambda x: x.name == name, fields(options)), None)
        if option is None:
            continue

        if not equals:
            if option.type == bool:
                setattr(options, name, True)
            else:
                raise Exception('Option %r requires a value' % name)

        if option.type == bool or get_args(option.type) == (bool, type(None)):
            setattr(options, name, value.lower() not in ("false", "0", "f"))
        elif option.type == int or get_args(option.type) == (int, type(None)):
            setattr(options, name, int(value))
        elif option.type == float or get_args(option.type) == (float, type(None)):
            setattr(options, name, float(value))
        elif option.type == str or get_args(option.type) == (str, type(None)):
            setattr(options, name, value)
        else:
            raise Exception('Complex types are not implemented %r: %r (%s)' % (name, value, option.type))
