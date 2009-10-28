from distutils.core import setup

setup(

name='frontik',
version='0.1',
      
package_dir = {'': 'src'},
packages = ['frontik', 'frontik.proto'],
      
scripts = ['src/frontik_srv.py'],

#data_files= [('')]
)