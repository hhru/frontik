# coding=utf-8

import lxml.etree as etree

from frontik.future import Future
from frontik.responses import FailedRequestException, RequestResult


class Doc(object):
    __slots__ = ('root_node_name', 'root_node', 'data')

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

    def is_empty(self):
        return len(self.data) == 0

    def clear(self):
        self.data = []

    @staticmethod
    def get_error_node(exception):
        return etree.Element('error', **{k: str(v) for k, v in exception.attrs.iteritems()})

    def to_etree_element(self):
        if self.root_node is not None:
            if isinstance(self.root_node, etree._Element):
                res = self.root_node
            elif isinstance(self.root_node, Doc):
                res = self.root_node.to_etree_element()
            else:
                raise ValueError('Cannot set {0} as Doc root node'.format(self.root_node))
        else:
            res = etree.Element(self.root_node_name)

        def chunk_to_element(chunk):
            if isinstance(chunk, list):
                for chunk_i in chunk:
                    for i in chunk_to_element(chunk_i):
                        yield i

            elif isinstance(chunk, RequestResult):
                for i in chunk_to_element(chunk.data):
                    yield i

            elif isinstance(chunk, Future):
                for i in chunk_to_element(chunk.get()):
                    yield i

            elif isinstance(chunk, FailedRequestException):
                yield self.get_error_node(chunk)

            elif isinstance(chunk, etree._Element):
                yield chunk

            elif isinstance(chunk, Doc):
                yield chunk.to_etree_element()

            elif isinstance(chunk, basestring):
                yield chunk

            elif chunk is not None:
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
        return etree.tostring(self.to_etree_element(), encoding='utf-8', xml_declaration=True)
