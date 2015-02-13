# coding=utf-8

import os

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
    def run(self):
        test.run(self)

        import nose
        import logging
        logging.disable(logging.CRITICAL)
        nose.main(argv=['tests', '-v'])

setup(
    name='frontik',
    version=__import__('frontik').__version__,
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=open('README.md').read(),
    url='https://github.com/hhru/frontik',
    cmdclass={'build_py': BuildHook, 'test': TestHook},
    packages=['frontik', 'frontik/producers', 'frontik/testing', 'frontik/testing/pages'],
    scripts=['scripts/frontik'],
    package_data={
        'frontik': ['debug/*.xsl'],
    },
    install_requires=[
        'nose',
        'lxml >= 2.3.2',
        'simplejson >= 2.3.2',
        'pycurl >= 7.19.0',
        'requests >= 0.8.2',
        'jinja2 >= 2.6',
        'tornado >= 3, <= 3.2.2-hh99',
        'tornado_util >= 0.7.6',
    ],
    tests_require=[
        'pep8',
    ],
    dependency_links=[
        'https://github.com/hhru/tornado-util/archive/master.zip#egg=tornado_util-0.7.6',
        'https://github.com/hhru/tornado/archive/HH-41232.zip#egg=tornado-3.2.2-hh1',
    ],
    zip_safe=False
)
