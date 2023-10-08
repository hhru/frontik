import os
import shutil
import tempfile
import unittest

from tests import FRONTIK_ROOT
from tests.instances import FrontikTestInstance, common_frontik_start_options

FRONTIK_RUN = f'{FRONTIK_ROOT}/frontik-test'
TEST_PROJECTS = f'{FRONTIK_ROOT}/tests/projects'


class TestLogToFile(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_log_dir = tempfile.mkdtemp()
        self.service = FrontikTestInstance(
            f'{FRONTIK_RUN} --app=tests.projects.consul_mock_app {common_frontik_start_options} '
            f' --config={TEST_PROJECTS}/frontik_consul_mock.cfg --log_dir={self.tmp_log_dir} --log_level=debug',
            allow_to_create_log_files=True,
        )

    def tearDown(self) -> None:
        self.service.stop()
        shutil.rmtree(self.tmp_log_dir, ignore_errors=True)

    def test_log_dir_is_not_empty(self) -> None:
        self.service.start()
        self.service.stop()
        dir_contents = os.listdir(self.tmp_log_dir)
        if not dir_contents:
            self.fail('No log files')
        empty_files = [f for f in dir_contents if os.stat(os.path.join(self.tmp_log_dir, f)).st_size == 0]
        if empty_files:
            self.fail(f'Empty log files: {empty_files}')
