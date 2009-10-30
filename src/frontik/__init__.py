# -*- coding: utf-8 -*-

# реализация ElementTree
import xml.etree.ElementTree as etree

from doc import Doc, DocResponse
from util import make_url

# реализация сервера
from proto_impl.http_client import http_get
from proto_impl.http_server import server_main