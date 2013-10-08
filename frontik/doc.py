# -*- coding: utf-8 -*-

import cStringIO

import lxml.etree as etree

import frontik.future


class Doc(object):
    def __init__(self, root_node_name='doc', root_node=None):
        self.root_node_name = root_node_name
        self.root_node = root_node
        self.data = []
        
    def put(self, chunk):
        if isinstance(chunk, list):
            self.data.extend(chunk)
        else:
            self.data.append(chunk)
        return self

    def _finalize_data(self):
        def chunk_to_string(chunk):
            if isinstance(chunk, etree._Element):
                yield etree.tostring(chunk)
            elif isinstance(chunk, Doc):
                for i in chunk._finalize_data():
                    yield i
            elif isinstance(chunk, list):
                for i in chunk:
                    for x in chunk_to_string(i):
                        yield x
            else:
                yield chunk
        
        for chunk in self.data:
            if isinstance(chunk, frontik.future.FutureVal):
                val = chunk.get()
            else:
                val = chunk
            
            for i in chunk_to_string(val):
                yield i

    def to_etree_element(self):
        if self.root_node is not None:
            res = self.root_node
        else:
            res = etree.Element(self.root_node_name)

        def chunk_to_element(chunk):
            # XXX изменится, при смене библиотеки!
            if isinstance(chunk, list):
                for chunk_i in chunk:
                    for i in chunk_to_element(chunk_i):
                        yield i

            elif isinstance(chunk, frontik.future.FutureVal):
                for i in chunk_to_element(chunk.get()):
                    yield i

            elif isinstance(chunk, etree._Element):
                yield chunk

            elif isinstance(chunk, Doc):
                yield chunk.to_etree_element()

            elif isinstance(chunk, basestring):
                yield chunk

            else:
                yield str(chunk)

        last_element = None
        for chunk_element in chunk_to_element(self.data):

            if isinstance(chunk_element, basestring):
                if not last_element is None:
                    if last_element.tail:
                        last_element.tail += chunk_element
                    else:
                        last_element.tail = chunk_element
                else:
                    if res.text:
                        res.text += chunk_element
                    else:
                        res.text = chunk_element

            else:
                res.append(chunk_element)
                last_element = chunk_element

        return res

    def to_string(self):
        return etree_to_xml(self.to_etree_element())


def etree_to_xml(string):
    sio = cStringIO.StringIO()
    etree.ElementTree(string).write(sio, encoding='utf-8', xml_declaration=True)
    return sio.getvalue()
