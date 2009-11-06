# -*- coding: utf-8 -*-

# frontik реализует следующий внешний API

# etree - модуль, который используется как реализация ElementTree
import xml.etree.ElementTree as etree

# Doc, DocResponse классы для формирования XML-ответа
from doc import Doc, DocResponse
from util import make_url

# реализация сервера
#from proto_impl.http_client import http_get
#from proto_impl.http_server import server_main

from proto_impl.http_client import http_get
from coev_impl.http_server import server_main