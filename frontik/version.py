import re
try:
    ver_path = __file__.rsplit("/", 2)[0]
    deb_path = ver_path + "/debian/changelog"
    changelog = open(deb_path, "r")
    regmatch = re.match("frontik \((.*)\).*", changelog.readline())
    version = regmatch.groups()[0]
    changelog.close()
except:
    version = 'DEVELOPMENT'

