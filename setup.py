import pathlib

from setuptools import setup, find_packages

root_dir = pathlib.Path(__file__).parent

PACKAGE_INFO = {}
version_file = (root_dir / 'frontik' / 'version.py').read_text()
exec(version_file, PACKAGE_INFO)

with (root_dir / 'requirements.txt').open('r') as requirements_txt:
    install_requirements = [requirement.strip() for requirement in requirements_txt]

with (root_dir / 'requirements_venv.txt').open('r') as requirements_vent_txt:
    dev_requirements = [requirement.strip() for requirement in requirements_vent_txt]

setup(
    name='frontik',
    version=PACKAGE_INFO['version'],
    description='Frontik is an asyncronous Tornado-based application server',
    long_description=(root_dir / 'README.md').read_text(),
    url='https://github.com/hhru/frontik',

    packages=find_packages(exclude=['tests*']),
    package_data={
        'frontik': ['debug/*.xsl'],
    },
    scripts=['scripts/frontik'],
    python_requires='>=3.8',
    install_requires=install_requirements,
    test_suite='tests',
    tests_require=dev_requirements,
    extras_require={
        'sentry': ['raven'],
        'kafka': ['aiokafka'],
    },
    zip_safe=False
)
