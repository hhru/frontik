import base64
import os
import random
import socket
from itertools import chain

from tornado.escape import to_unicode, utf8

FRONTIK_ROOT = os.path.dirname(os.path.dirname(__file__))


def create_basic_auth_header(credentials: str) -> str:
    return f'Basic {to_unicode(base64.b64encode(utf8(credentials)))}'


def find_free_port(from_port: int = 9000, to_port: int = 10000) -> int:
    random_start = random.randint(from_port, to_port)

    for port in chain(range(random_start, to_port), range(from_port, random_start)):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('', port))
            break
        except Exception:
            pass
        finally:
            s.close()
    else:
        msg = f'No empty port in range {from_port}..{to_port} for frontik test instance'
        raise AssertionError(msg)

    return port
