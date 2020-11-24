import sys

from setuptools import setup
from setuptools.command.test import test

from frontik.version import version


class TestHook(test):
    user_options = [('with-coverage', 'c', 'Run test suite with coverage')]

    def initialize_options(self):
        self.with_coverage = False
        test.initialize_options(self)

    def run_tests(self):
        import pytest
        sys.exit(pytest.main(['tests', '--tb', 'native']))


with open('requirements.txt', 'r') as requirements_txt:
    install_requirements = [requirement.strip() for requirement in requirements_txt]
    print("foooo")

setup(
    name='frontik',
    version=version,
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=open('README.md').read(),
    url='https://github.com/hhru/frontik',
    cmdclass={
        'test': TestHook
    },
    packages=[
        'frontik', 'frontik/loggers', 'frontik/producers', 'frontik/integrations'
    ],
    package_data={
        'frontik': ['debug/*.xsl'],
    },
    scripts=['scripts/frontik'],
    python_requires='>=3.7',
    install_requires=install_requirements,
    test_suite='tests',
    tests_require=[
        'pytest <= 3.8.2',
        'pycodestyle == 2.5.0',
        'requests <= 2.20.0',
        'lxml-asserts',
        'tornado-httpclient-mock',
    ],
    extras_require={
        'sentry': ['raven'],
        'kafka': ['aiokafka'],
    },
    zip_safe=False
)
