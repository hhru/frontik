from distutils.core import setup

setup(
    name='frontik',
    version='2.8.0dev',

    package_dir = {'': 'src'},
    packages = ['frontik'],

    scripts = ['src/frontik_srv.py']
)
