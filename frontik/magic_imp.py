# coding=utf-8

import sys
import os.path
import imp
import functools

import logging

log = logging.getLogger('frontik.imp')


def gen_module_name(app_name, module_name=None):
    if module_name:
        return 'frontik.imp.{0}.{1}'.format(app_name, module_name)
    else:
        return 'frontik.imp.{0}'.format(app_name)


class FrontikAppImporter(object):
    def __init__(self, name, root):
        self.root = root
        self.name = name

    def get_probable_module_filenames(self, module_name):
        module_name_as_path = os.path.join(*module_name.split('.'))

        app_module_probable_filenames = [
            os.path.join(self.root, module_name_as_path, '__init__.py'),
            os.path.join(self.root, module_name_as_path, 'index.py'),
            os.path.join(self.root, '{0}.py'.format(module_name_as_path))]

        return app_module_probable_filenames

    def imp_app_module(self, module_name):
        """
        module_path :: 'pages.index'
        """
        app_module_name = gen_module_name(self.name, module_name)

        if app_module_name in sys.modules:
            log.debug('get %s from module cache', app_module_name)
            return sys.modules[app_module_name]

        app_module_probable_filenames = self.get_probable_module_filenames(module_name)

        for app_module_filename in app_module_probable_filenames:
            if os.path.exists(app_module_filename):
                break
        else:
            raise ImportError(
                '{module_name} module was not found in {app_name}, {app_module_filenames} expected'.format(
                    module_name=module_name,
                    app_name=self.name,
                    app_module_filenames=app_module_probable_filenames))

        log.debug('importing %s from %s', app_module_name, app_module_filename)

        module = imp.new_module(app_module_name)
        sys.modules[module.__name__] = module

        module.__file__ = app_module_filename
        module.frontik_import = functools.partial(self.in_module_import, module)

        try:
            execfile(app_module_filename, module.__dict__)
        except:
            del sys.modules[module.__name__]
            exc_class, exc, tb = sys.exc_info()
            reraised_exception = Exception('failed to load module "{0}", original exception was: {1}'.format(
                module.__name__, exc or exc_class))
            raise reraised_exception.__class__, reraised_exception, tb

        return module

    def in_module_import(self, app_module, module_name):
        prev_mod = app_module

        sub_path = []
        for sub_name in module_name.split('.'):
            sub_path.append(sub_name)
            full_sub_name = '.'.join(sub_path)

            sub_module = self.imp_app_module(full_sub_name)
            setattr(prev_mod, sub_name, sub_module)

            prev_mod = sub_module

        return sub_module
