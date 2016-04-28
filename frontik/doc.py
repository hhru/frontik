# coding=utf-8

import logging

import lxml.etree as etree

from tornado.concurrent import Future

from frontik.compat import basestring_type, iteritems
from frontik.http_client import RequestResult

future_logger = logging.getLogger('frontik.future')


def _is_valid_element(node):
    if not isinstance(node, etree._Element):
        return False

    if node.tag is etree.PI or node.tag is etree.Comment or node.tag is etree.Entity:
        return False

    return True


class Doc(object):
    __slots__ = ('root_node', 'data', 'logger')

    def __init__(self, root_node='doc', logger=None):
        if isinstance(root_node, basestring_type):
            root_node = etree.Element(root_node)

        if not (_is_valid_element(root_node) or isinstance(root_node, Doc)):
            raise TypeError('Cannot set {} as root node'.format(root_node))

        self.root_node = root_node
        self.logger = logger if logger is not None else future_logger
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
        return etree.Element('error', **{k: str(v) for k, v in iteritems(exception.attrs)})

    def to_etree_element(self):
        res = self.root_node.to_etree_element() if isinstance(self.root_node, Doc) else self.root_node

        def chunk_to_element(chunk):
            if isinstance(chunk, list):
                for chunk_i in chunk:
                    for i in chunk_to_element(chunk_i):
                        yield i

            elif hasattr(chunk, 'to_etree_element'):
                yield chunk.to_etree_element()

            elif isinstance(chunk, RequestResult):
                if chunk.exception is not None:
                    yield self.get_error_node(chunk.exception)
                else:
                    for i in chunk_to_element(chunk.data):
                        yield i

            elif isinstance(chunk, Future):
                if chunk.done():
                    for i in chunk_to_element(chunk.result()):
                        yield i
                else:
                    self.logger.info('unresolved Future in Doc')

            elif isinstance(chunk, etree._Element):
                yield chunk

            elif isinstance(chunk, basestring_type):
                yield chunk

            elif chunk is not None:
                yield str(chunk)

        last_element = None
        for chunk_element in chunk_to_element(self.data):

            if isinstance(chunk_element, basestring_type):
                if last_element is not None:
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
