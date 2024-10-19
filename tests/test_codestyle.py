import os
import subprocess

import mypy.api

ROOT = os.path.dirname(os.path.dirname(__file__))
MODULES = ['frontik', 'tests']


def test_mypy():
    code_paths = [f'{ROOT}/{m}' for m in MODULES]
    out, err, exit_code = mypy.api.run(['--config-file', f'{ROOT}/pyproject.toml', *code_paths])
    assert exit_code == 0, out


def test_ruff():
    modules = ' '.join(MODULES)
    opts = ''
    completed_proc = subprocess.run(f'cd {ROOT}; ruff check {opts} {modules}', capture_output=True, shell=True)
    code = completed_proc.returncode
    out = completed_proc.stdout.decode('utf-8')
    assert code == 0, out


def test_ruff_format():
    modules = ' '.join(MODULES)
    opts = '--check'
    completed_proc = subprocess.run(f'cd {ROOT}; ruff format {opts} {modules}', capture_output=True, shell=True)
    code = completed_proc.returncode
    out = completed_proc.stdout.decode('utf-8')
    assert code == 0, out
