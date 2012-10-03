import os
import re

try:
    deb_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'debian/changelog')
    with open(deb_path, 'r') as changelog:
        regmatch = re.match(r'frontik \((.*)\).*', changelog.readline())
        version = regmatch.groups()[0]
except:
    version = 'DEVELOPMENT'
