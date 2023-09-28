from __future__ import annotations
import lxml.etree as etree
from typing import TYPE_CHECKING
from tornado.concurrent import Future
if TYPE_CHECKING:
    from typing import Any, Generator


def _is_valid_element(node: Any) -> bool:
    if not isinstance(node, etree._Element):
        return False

    if node.tag is etree.PI or node.tag is etree.Comment or node.tag is etree.Entity:
        return False

    return True


class Doc:
    __slots__ = ('root_node', 'data')

    def __init__(self, root_node:Any='doc') -> None:
        if isinstance(root_node, str):
            root_node = etree.Element(root_node)

        if not (_is_valid_element(root_node) or isinstance(root_node, Doc)):
            raise TypeError(f'Cannot set {root_node} as root node')

        self.root_node = root_node
        self.data: list = []

    def put(self, chunk: Any) -> Doc:
        if isinstance(chunk, list):
            self.data.extend(chunk)
        else:
            self.data.append(chunk)

        return self

    def is_empty(self) -> bool:
        return len(self.data) == 0

    def clear(self):
        self.data = []

    def to_etree_element(self) -> etree.Element:
        res = self.root_node.to_etree_element() if isinstance(self.root_node, Doc) else self.root_node

        def chunk_to_element(chunk:Any) -> Generator:
            if isinstance(chunk, list):
                for chunk_i in chunk:
                    for i in chunk_to_element(chunk_i):
                        yield i

            elif hasattr(chunk, 'to_etree_element'):
                etree_element = chunk.to_etree_element()
                if etree_element is not None:
                    yield etree_element

            elif isinstance(chunk, Future):
                if chunk.done() and chunk.exception() is None:
                    for i in chunk_to_element(chunk.result()):
                        yield i

            elif isinstance(chunk, etree._Element):
                yield chunk

            elif chunk is not None:
                raise ValueError(f'Unexpected value of type {type(chunk)} in doc')

        for chunk_element in chunk_to_element(self.data):
            res.append(chunk_element)

        return res

    def to_string(self) -> bytes:
        return etree.tostring(self.to_etree_element(), encoding='utf-8', xml_declaration=True)
