import contextvars
import threading


class _Context:
    __slots__ = ('request', 'request_id', 'handler_name', 'log_handler')

    def __init__(self, request, request_id):
        self.request = request
        self.request_id = request_id
        self.handler_name = None
        self.log_handler = None


_context = contextvars.ContextVar('context', default=_Context(None, None))


def initialize(request, request_id):
    return _context.set(_Context(request, request_id))


def reset(token):
    _context.reset(token)


def get_request():
    return _context.get().request


def get_request_id():
    return _context.get().request_id


def get_handler_name():
    return _context.get().handler_name


def set_handler_name(handler_name):
    _context.get().handler_name = handler_name


def get_log_handler():
    return _context.get().log_handler


def set_log_handler(log_handler):
    _context.get().log_handler = log_handler
