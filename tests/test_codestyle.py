import os
import subprocess
import sys

import mypy.api

ROOT = os.path.dirname(os.path.dirname(__file__))


def test_simple_error():
    assert 1 == 0, 'mega error message'


def test_mypy():
    code_paths = [f'{ROOT}/frontik', f'{ROOT}/tests']
    out, err, exit_code = mypy.api.run(['--config-file', f'{ROOT}/pyproject.toml'] + code_paths)
    sys.stdout.write(out)
    sys.stderr.write(err)
    assert 0 == exit_code, out


def test_ruff():
    completed_proc = subprocess.run(f'(cd {ROOT}; ruff frontik tests)', capture_output=True, shell=True)
    assert completed_proc.returncode == 0, completed_proc.stdout


def test_black():
    completed_proc = subprocess.run(f'(cd {ROOT}; black --check frontik tests)', capture_output=True, shell=True)
    assert completed_proc.returncode == 0, completed_proc.stderr
