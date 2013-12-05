# coding=utf-8

import os

from setuptools import setup
from setuptools.command.build_py import build_py

from frontik import version


class BuildHook(build_py):
    def run(self):
        build_py.run(self)

        build_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), self.build_lib, 'frontik')
        with open(os.path.join(build_dir, 'version.py'), 'w') as version_file:
            version_file.write('version = "{0}"\n'.format(version))

setup(
    name='frontik',
    version=__import__('frontik').__version__,
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=open('README.md').read(),
    url='https://github.com/hhru/frontik',
    cmdclass={'build_py': BuildHook},
    packages=['frontik', 'frontik/testing', 'frontik/testing/pages'],
    scripts=['scripts/frontik'],
    package_data={
        'frontik': ['*.xsl'],
    },
    install_requires=[
        'lxml >= 2.2.8, < 2.3a',
        'tornado'
    ],
    zip_safe=False
)
