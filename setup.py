# coding=utf-8

import os
import sys

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.test import test

from frontik import version


class BuildHook(build_py):
    def run(self):
        build_py.run(self)

        build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.build_lib, 'frontik')
        with open(os.path.join(build_dir, 'version.py'), 'w') as version_file:
            version_file.write('version = "{0}"\n'.format(version))


class TestHook(test):
    user_options = [('with-coverage', 'c', 'Run test suite with coverage')]

    def initialize_options(self):
        self.with_coverage = False
        test.initialize_options(self)

    def run_tests(self):
        import nose
        nose.main(argv=['nosetests', 'tests/', '-v', '--logging-clear-handlers'])


install_requires = [
    'jinja2 >= 2.8',
    'lxml >= 3.5.0',
    'pycurl >= 7.43.0',
    'simplejson >= 3.8.1',
    'tornado >= 4.5, < 4.6',
]

if sys.version_info < (3, 2):
    install_requires.append('futures')

setup(
    name='frontik',
    version=__import__('frontik').__version__,
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=open('README.md').read(),
    url='https://github.com/hhru/frontik',
    cmdclass={
        'build_py': BuildHook,
        'test': TestHook
    },
    packages=[
        'frontik', 'frontik/loggers', 'frontik/producers', 'frontik/http_client'
    ],
    package_data={
        'frontik': ['debug/*.xsl'],
    },
    install_requires=install_requires,
    test_suite='tests',
    tests_require=[
        'nose',
        'pycodestyle == 2.2.0',
        'requests <= 2.9.1',
        'lxml-asserts',
        'tornado-httpclient-mock',
    ],
    dependency_links=[
        'https://github.com/hhru/tornado/archive/master.zip',
    ],
    extras_require={
        'sentry': ['raven']
    },
    zip_safe=False
)
