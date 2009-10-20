import os
import os.path
import xml.etree.ElementTree as et

def find_xml(base_dir):
    for n in os.listdir(base_dir):
        fn = os.path.join(base_dir, n)
        
        if n.endswith('.xml'):
            yield os.path.normpath(fn)
        elif os.path.isdir(fn):
            for i in find_xml(fn):
                yield i

def find_deps(xml_file):
    try:
        xml = et.parse(file(xml_file))
    except:
        pass
    else:
        xml_bn = os.path.dirname(xml_file)
        for xi in xml.findall('{http://www.w3.org/2001/XInclude}include'):
            xi_href_raw = xi.get('href')
            xi_href_norm = os.path.normpath(os.path.join(xml_bn, xi_href_raw))
            yield xi_href_norm

for xml_file in find_xml('.'):
    for dep in find_deps(xml_file):
        print xml_file, '->', dep