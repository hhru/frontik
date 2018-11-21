import jinja2

from frontik.app import FrontikApplication
from frontik.util import get_abs_path
from tornado.options import options

from . import config
from .pages import handler_404


class TestApplication(FrontikApplication):
    def application_config(self):
        return config

    def application_urls(self):
        return config.urls

    def application_404_handler(self, request):
        return handler_404.Page, {}

    def get_jinja_environment(self):
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(get_abs_path(self.app_root, options.jinja_template_root)),
        )

        env.globals['custom_env_function'] = lambda: 'custom_env_function_value'

        return env
