"""
usage: script dir_with_xml
"""

import os.path
import xml.etree.ElementTree as et
import sys

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

import pygraphviz
from collections import defaultdict

graph = pygraphviz.AGraph(directed=True, concentrate="true", ranksep="15")


dir_subgraphs = defaultdict(list)
edges = []

for xml_file in find_xml(sys.argv[1]):
    dir_subgraphs[os.path.dirname(xml_file)].append(xml_file)
    
    for dep in find_deps(xml_file):
        edges.append((xml_file, dep))
        print xml_file, '->', dep

for subgraph, nodes in dir_subgraphs.iteritems():
    graph.add_nodes_from(nodes, shape='box', color='red')
    graph.add_subgraph(nodes, 'cluster/' + subgraph)
    
graph.add_edges_from(edges)

graph.write('xhh.dot')
graph.draw('xhh_dot.svg', format='svg', prog='dot')
graph.draw('xhh_twopi.png', format='png', prog='twopi')
graph.draw('xhh_twopi.svg', format='svg', prog='twopi')
