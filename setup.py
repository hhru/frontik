# coding=utf-8

import os

from setuptools import setup
from setuptools.command.install import install

from frontik.version import parse_version_from_changelog


class InstallHook(install):
    def run(self):
        install.run(self)

        frontik_build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.build_lib, 'frontik')
        with open(os.path.join(frontik_build_dir, 'version.py'), 'w') as version_file:
            version_file.write('version = "{0}"\n'.format(parse_version_from_changelog()))

setup(
    name='frontik',
    version=__import__('frontik').__version__,
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=open('README.md').read(),
    url='https://github.com/hhru/frontik',
    cmdclass={'install': InstallHook},
    packages=['frontik', 'frontik/testing', 'frontik/testing/pages'],
    scripts=['scripts/frontik'],
    package_data={
        'frontik': ['*.xsl'],
    },
    install_requires=[
        'lxml >= 2.2.8, < 2.3a',
        'tornado_util'
    ],
    zip_safe=False
)
