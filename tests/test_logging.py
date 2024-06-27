import json
import re
import socket
from collections import defaultdict

import pytest
from tornado.escape import to_unicode

from tests import FRONTIK_ROOT
from tests.instances import FrontikTestInstance

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'
TEST_PROJECTS = f'{FRONTIK_ROOT}/tests/projects'


class TestSyslog:
    test_app: FrontikTestInstance
    s: socket.socket

    @classmethod
    def setup_class(cls):
        cls.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.s.settimeout(0.1)
        cls.s.bind(('', 0))

        port = cls.s.getsockname()[1]

        cls.test_app = FrontikTestInstance(
            f'{FRONTIK_RUN} --app=tests.projects.test_app.TestApplication --config={TEST_PROJECTS}/frontik_debug.cfg '
            f'--syslog=true --consul_enabled=False --syslog_host=127.0.0.1 --syslog_tag=test'
            f' --log_level=debug --syslog_port={port}',
        )

    @classmethod
    def teardown_class(cls):
        cls.test_app.stop()

    def test_send_to_syslog(self):
        self.test_app.get_page('log')

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
            assert re.match(syslog_line_regexp, log)

            match = re.match(syslog_line_regexp, log)
            if match is not None:
                priority, tag, message = match.groups()
                parsed_logs[tag].append({'priority': priority, 'message': message})

        expected_service_logs = [
            {'priority': '14', 'message': {'lvl': 'INFO', 'logger': r'handler', 'msg': 'requested url: /log'}},
            {'priority': '15', 'message': {'lvl': 'DEBUG', 'logger': r'handler', 'msg': 'debug'}},
            {'priority': '14', 'message': {'lvl': 'INFO', 'logger': r'handler', 'msg': 'info'}},
            {
                'priority': '11',
                'message': {
                    'lvl': 'ERROR',
                    'logger': r'handler',
                    'msg': 'exception',
                    'exception': '.*raise Exception.*',
                },
            },
            {
                'priority': '11',
                'message': {
                    'lvl': 'ERROR',
                    'logger': r'handler',
                    'msg': 'error',
                    'exception': r".*handler\.log\.error\('error', stack_info=True\)",
                },
            },
            {'priority': '10', 'message': {'lvl': 'CRITICAL', 'logger': r'handler', 'msg': 'critical'}},
        ]

        self.assert_json_logs_match(expected_service_logs, parsed_logs['test/service.slog/'])

        expected_service_logs = [
            {
                'priority': '14',
                'message': {
                    'lvl': 'INFO',
                    'logger': r'server',
                    'msg': r'starting application tests\.projects\.test_app',
                },
            },
        ]

        self.assert_json_logs_match(expected_service_logs, parsed_logs['test/server.slog/'])

        expected_requests_logs = [
            {
                'priority': '14',
                'message': {'ip': '.+', 'rid': '.+', 'status': '200', 'time': '.+', 'method': 'GET', 'uri': '/log'},
            },
        ]

        self.assert_json_logs_match(expected_requests_logs, parsed_logs['test/requests.slog/'])

        expected_custom_logs = [
            {
                'priority': '10',
                'message': r'\[\d+\] [\d-]+ [\d:,]+ CRITICAL '
                r'custom_logger\.tests\.projects\.test_app\.pages\.log\.get_page\.\w+: fatal',
            },
        ]

        self.assert_text_logs_match(expected_custom_logs, parsed_logs['test/custom_logger.log/'])

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
