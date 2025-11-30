import json
import logging
import os
import re
import shutil
import socket
import tempfile
from collections import defaultdict
from logging.handlers import SysLogHandler
from typing import Any

import pytest
from tornado.escape import to_unicode

from frontik.app import FrontikApplication
from frontik.loggers import _configure_file, _configure_syslog, bootstrap_logger
from frontik.options import options
from frontik.routing import router
from frontik.testing import FrontikTestBase
from tests import FRONTIK_ROOT

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'
TEST_PROJECTS = f'{FRONTIK_ROOT}/tests/projects'
handler_logger = logging.getLogger('handler')
service_logger = logging.getLogger('service')
custom_logger = logging.getLogger('custom_logger')


def add_syslog_handler_for_logger(logger_name: str) -> None:
    logger = logging.getLogger(logger_name)
    handler = _configure_syslog(logger)[0]
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)


def add_syslog_handler_for_root_logger() -> None:
    handler = _configure_syslog(service_logger)[0]
    handler.setLevel(logging.DEBUG)
    logging.root.addHandler(handler)


def remove_syslog_handler_from_logger(logger_name: str) -> None:
    logger = logging.getLogger(logger_name)
    logger.handlers = [handler for handler in handler_logger.handlers if not isinstance(handler, SysLogHandler)]


@router.get('/log')
async def get_page():
    handler_logger.debug('debug')
    handler_logger.info('info')

    try:
        raise Exception('test')
    except Exception:
        handler_logger.exception('exception')
        handler_logger.error('error')  # stack_info = True should be added

    handler_logger.critical('critical')
    custom_logger.fatal('fatal')


class TestSyslog(FrontikTestBase):
    s: socket.socket

    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    @classmethod
    def setup_class(cls):
        cls.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.s.settimeout(0.1)
        cls.s.bind(('', 0))

        port = cls.s.getsockname()[1]

        options.log_write_appender_name = True
        options.syslog = True
        options.syslog_port = port
        options.syslog_tag = 'test'
        options.service_name = 'app'

        add_syslog_handler_for_logger('server')
        add_syslog_handler_for_root_logger()
        add_syslog_handler_for_logger('requests')
        add_syslog_handler_for_logger('handler')
        bootstrap_logger('custom_logger', logger_level=logging.DEBUG, use_json_formatter=False)

    @classmethod
    def teardown_class(cls):
        options.syslog = False

        remove_syslog_handler_from_logger('server')
        remove_syslog_handler_from_logger('service')
        remove_syslog_handler_from_logger('requests')
        remove_syslog_handler_from_logger('handler')
        remove_syslog_handler_from_logger('custom_logger')

        cls.s.close()

    async def test_send_to_syslog(self):
        await self.fetch('/log')

        logs = []

        try:
            line = self.s.recv(1024 * 24)
            while line:
                logs.append(to_unicode(line))
                line = self.s.recv(1024 * 24)
        except socket.timeout:
            pass
        finally:
            self.s.close()

        syslog_line_regexp = r'<(?P<priority>\d+)>(?P<tag>[^:]+): (?P<message>.*)\x00'
        parsed_logs = defaultdict(list)
        for log in logs:
            match = re.match(syslog_line_regexp, log)
            assert match is not None
            priority, tag, message = match.groups()
            parsed_logs[tag].append({'priority': priority, 'message': message})

        expected_service_logs = [
            {
                'priority': '14',
                'message': {
                    'lvl': 'INFO',
                    'logger': r'handler',
                    'msg': 'requested url: /log',
                    'appender': 'service.slog',
                },
            },
            {
                'priority': '15',
                'message': {'lvl': 'DEBUG', 'logger': r'handler', 'msg': 'debug', 'appender': 'service.slog'},
            },
            {
                'priority': '14',
                'message': {'lvl': 'INFO', 'logger': r'handler', 'msg': 'info', 'appender': 'service.slog'},
            },
            {
                'priority': '11',
                'message': {
                    'lvl': 'ERROR',
                    'logger': r'handler',
                    'msg': 'exception',
                    'exception': '.*raise Exception.*',
                },
                'appender': 'service.slog',
            },
            {
                'priority': '11',
                'message': {
                    'lvl': 'ERROR',
                    'logger': r'handler',
                    'msg': 'error',
                },
                'appender': 'service.slog',
            },
            {
                'priority': '10',
                'message': {'lvl': 'CRITICAL', 'logger': r'handler', 'msg': 'critical', 'appender': 'service.slog'},
            },
        ]

        self.assert_json_logs_match(expected_service_logs, parsed_logs['test/service.slog/'])

        expected_service_logs = [
            {
                'priority': '14',
                'message': {
                    'lvl': 'INFO',
                    'logger': r'server',
                    'msg': r'Successfully inited application app',
                    'appender': 'server.slog',
                },
            },
        ]

        self.assert_json_logs_match(expected_service_logs, parsed_logs['test/server.slog/'])

        expected_requests_logs = [
            {
                'priority': '14',
                'message': {
                    'ip': '.+',
                    'rid': '.+',
                    'status': '200',
                    'time': '.+',
                    'method': 'GET',
                    'uri': '/log',
                    'appender': 'requests.slog',
                },
            },
        ]

        self.assert_json_logs_match(expected_requests_logs, parsed_logs['test/requests.slog/'])

        expected_custom_logs = [
            {
                'priority': '10',
                'message': r'\["appender":"service.slog"\] \[\d+\] [\d-]+ [\d:,]+ CRITICAL '
                r'custom_logger\.tests\.test_logging\.get_page\.tests\.test_logging\.get_page: fatal',  # seems weird
            },
        ]

        self.assert_text_logs_match(expected_custom_logs, parsed_logs['test/custom_logger.rlog/'])

    @staticmethod
    def assert_json_logs_match(expected_logs: list, parsed_logs: list) -> None:
        for expected_log in expected_logs:
            for actual_log in parsed_logs:
                priority = actual_log['priority']
                message = json.loads(actual_log['message'])

                if priority == expected_log['priority'] and all(
                    re.match(v, str(message[k]), re.DOTALL) for k, v in expected_log['message'].items()
                ):
                    break
            else:
                pytest.fail(f'Log message not found: {expected_log}')

    @staticmethod
    def assert_text_logs_match(expected_logs: list, parsed_logs: list) -> None:
        for expected_log in expected_logs:
            for actual_log in parsed_logs:
                priority = actual_log['priority']
                message = actual_log['message']

                if priority == expected_log['priority'] and re.match(expected_log['message'], message):
                    break
            else:
                pytest.fail(f'Log message not found: {expected_log}')


class TestLogToFile(FrontikTestBase):
    tmp_log_dir: str
    handler: Any

    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    @classmethod
    def setup_class(cls):
        cls.tmp_log_dir = tempfile.mkdtemp()
        options.log_dir = cls.tmp_log_dir
        options.log_write_appender_name = True
        server_logger = logging.getLogger('server')
        cls.handler = _configure_file(server_logger)[0]
        server_logger.addHandler(cls.handler)

    @classmethod
    def teardown_class(cls):
        shutil.rmtree(cls.tmp_log_dir, ignore_errors=True)
        options.log_dir = None
        logging.getLogger('server').removeHandler(cls.handler)

    def test_log_dir_is_not_empty(self) -> None:
        dir_contents = os.listdir(self.tmp_log_dir)
        if not dir_contents:
            assert False, 'No log files'

        empty_files = [f for f in dir_contents if os.stat(os.path.join(self.tmp_log_dir, f)).st_size == 0]
        if empty_files:
            assert False, f'Empty log files: {empty_files}'
