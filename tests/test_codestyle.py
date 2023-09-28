import os
import subprocess

import mypy.api

ROOT = os.path.dirname(os.path.dirname(__file__))
MODULES = ['frontik', 'tests']


# def test_simple_error(files_for_lint):
#     print('--------------')
#     print(f'------{files_for_lint}--------')
#     # completed_proc = subprocess.run(
#     #     f'cd {ROOT}; git diff --diff-filter=d --name-only  master -- "***.py"', capture_output=True, shell=True
#     # )
#     # code = completed_proc.returncode
#     # out = completed_proc.stdout.decode('utf-8').splitlines()
#     # print(out)
#     assert 1 == 0, f'mega error message, files for lint {files_for_lint}'


def test_mypy():
    code_paths = [f'{ROOT}/{m}' for m in MODULES]
    # opts = [
    #     '--ignore-missing-imports',
    #     '--disallow-untyped-calls',
    #     '--disallow-incomplete-defs',
    #     '--check-untyped-defs',
    # ]
    # out, err, exit_code = mypy.api.run(opts + code_paths)
    out, err, exit_code = mypy.api.run(['--config-file', f'{ROOT}/pyproject.toml'] + code_paths)
    assert exit_code == 0, out


# def test_ruff():
#     modules = ' '.join(MODULES)
#     opts = ' '.join(
#         [
#             '--line-length 120',
#             # '--ignore F541,D300',
#             '--select E,F,W,I',
#         ]
#     )
#     completed_proc = subprocess.run(f'cd {ROOT}; ruff {opts} {modules}', capture_output=True, shell=True)
#     code = completed_proc.returncode
#     out = completed_proc.stdout.decode('utf-8')
#     assert code == 0, out
#
#
# def test_black():
#     modules = ' '.join(MODULES)
#     opts = ' '.join(
#         [
#             '--check',
#             '--diff',
#             '-l 120',
#             '-S',
#         ]
#     )
#     completed_proc = subprocess.run(f'cd {ROOT}; black {opts} {modules}', capture_output=True, shell=True)
#     code = completed_proc.returncode
#     out = completed_proc.stdout.decode('utf-8')
#     assert code == 0, out




# from functools import partial
# import os.path
# import unittest
#
# import pycodestyle
#
# from tests import FRONTIK_ROOT
#
#
# class TestPycodestyle(unittest.TestCase):
#     CHECKED_PATHS = ('frontik', 'tests', 'examples', 'frontik-test')
#
#     def test_pycodestyle(self) -> None:
#         style_guide = pycodestyle.StyleGuide(
#             show_pep8=False, show_source=True, max_line_length=120, ignore=['E731', 'W504']
#         )
#         result = style_guide.check_files(map(partial(os.path.join, FRONTIK_ROOT), TestPycodestyle.CHECKED_PATHS))
#         self.assertEqual(result.total_errors, 0, 'Pycodestyle found code style errors or warnings')
