import json
import re
import socket
import unittest
from collections import defaultdict

from tornado.escape import to_unicode

from .instances import FrontikTestInstance


class TestSyslog(unittest.TestCase):
    test_app = None

    @classmethod
    def setUpClass(cls):
        cls.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.s.settimeout(0.1)
        cls.s.bind(('', 0))

        port = cls.s.getsockname()[1]

        cls.test_app = FrontikTestInstance(
            './frontik-test --app=tests.projects.test_app --config=tests/projects/frontik_debug.cfg '
            f'--syslog=true --syslog_host=127.0.0.1 --syslog_port={port}'
        )

    @classmethod
    def tearDownClass(cls):
        cls.test_app.stop()

    def test_send_to_udp(self):
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
            self.assertRegex(log, syslog_line_regexp)

            match = re.match(syslog_line_regexp, log)
            priority, tag, message = match.groups()

            parsed_logs[tag].append({
                'priority': priority,
                'message': message
            })

        expected_service_logs = [
            {
                'priority': '14',
                'message': {
                    'lvl': 'INFO', 'logger': r'server', 'msg': r'starting application tests\.projects\.test_app'
                }
            },
            {
                'priority': '14',
                'message': {
                    'lvl': 'INFO', 'logger': r'frontik\.routing', 'msg': 'requested url: /log'
                }
            },
            {
                'priority': '15',
                'message': {
                    'lvl': 'DEBUG', 'logger': r'handler', 'msg': 'debug'
                }
            },
            {
                'priority': '14',
                'message': {
                    'lvl': 'INFO', 'logger': r'handler', 'msg': 'info'
                }
            },
            {
                'priority': '11',
                'message': {
                    'lvl': 'ERROR', 'logger': r'handler', 'msg': 'exception', 'exception': '.*raise Exception.*'
                }
            },
            {
                'priority': '11',
                'message': {
                    'lvl': 'ERROR', 'logger': r'handler', 'msg': 'error',
                    'exception': r".*self\.log\.error\('error', stack_info=True\)"
                }
            },
            {
                'priority': '10',
                'message': {
                    'lvl': 'CRITICAL', 'logger': r'handler', 'msg': 'critical'
                }
            },
        ]

        self.assert_json_logs_match(expected_service_logs, parsed_logs['service'])

        expected_requests_logs = [
            {
                'priority': '14',
                'message': {
                    'ip': '.+', 'rid': '.+', 'status': '200', 'time': '.+', 'method': 'GET', 'uri': '/log'
                }
            },
        ]

        self.assert_json_logs_match(expected_requests_logs, parsed_logs['requests'])

        expected_custom_logs = [
            {
                'priority': '10',
                'message': r'\[\d+\] [\d-]+ [\d:,]+ CRITICAL '
                           r'custom_logger\.tests\.projects\.test_app\.pages\.log\.Page\.\d+: fatal'
            },
        ]

        print(parsed_logs['custom_logger'])

        self.assert_text_logs_match(expected_custom_logs, parsed_logs['custom_logger'])

    def assert_json_logs_match(self, expected_logs, parsed_logs):
        for expected_log in expected_logs:
            for actual_log in parsed_logs:
                priority = actual_log['priority']
                message = json.loads(actual_log['message'])

                if (
                    priority == expected_log['priority'] and
                    all(re.match(v, str(message[k]), re.DOTALL) for k, v in expected_log['message'].items())
                ):
                    break
            else:
                self.fail(f'Log message not found: {expected_log}')

    def assert_text_logs_match(self, expected_logs, parsed_logs):
        for expected_log in expected_logs:
            for actual_log in parsed_logs:
                priority = actual_log['priority']
                message = actual_log['message']

                if priority == expected_log['priority'] and re.match(expected_log['message'], message):
                    break
            else:
                self.fail(f'Log message not found: {expected_log}')
