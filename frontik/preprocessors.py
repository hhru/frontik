# coding=utf-8


def preprocessor(function_or_list):
    """Creates a preprocessor decorator for `BaseHandler.get_page`, `BaseHandler.post_page` etc.

    Preprocessor is a function that accepts handler instance as its only parameter.
    Preprocessor can return a ``Future`` (any other value is ignored) and is considered
    finished when this ``Future`` is resolved.

    Several ``@preprocessor`` decorators are executed sequentially.

    Usage::
        @preprocessor
        def get_a(handler):
            future = Future()
            # Do something asynchronously
            return future

        @preprocessor
        def get_b(handler):
            # Do something
            return None

        class Page(PageHandler):
            @get_a
            @get_b
            # Can also be rewritten as:
            # @preprocessor([get_a, get_b])
            def get_page(self):
                pass

    When the ``Future`` returned by ``get_a`` is resolved, ``get_b`` is called.
    Finally, after ``get_b`` is executed, ``get_page`` will be called.
    """

    def preprocessor_decorator(func):
        if callable(function_or_list):
            _register_preprocessors(func, [function_or_list])
        else:
            for dep in reversed(function_or_list):
                dep(func)

        return func

    if callable(function_or_list):
        dep_name = function_or_list.__name__
    else:
        dep_name = [f.__name__ for f in function_or_list]

    preprocessor_decorator.func_name = 'preprocessor_decorator({})'.format(dep_name)

    return preprocessor_decorator


def _get_preprocessors(func):
    return getattr(func, '_preprocessors', [])


def _unwrap_preprocessors(preprocessors):
    return _get_preprocessors(preprocessor(preprocessors)(lambda: None))


def _register_preprocessors(func, preprocessors):
    setattr(func, '_preprocessors', preprocessors + _get_preprocessors(func))
