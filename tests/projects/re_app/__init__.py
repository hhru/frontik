# coding=utf-8

import jinja2

from frontik.app import FrontikApplication

from tests.projects.re_app import config


class TestApplication(FrontikApplication):
    def application_config(self):
        return config

    def application_urls(self):
        return config.urls

    def get_jinja_environment(self):
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.application_config().template_root),
        )

        env.globals['custom_env_function'] = lambda: 'custom_env_function_value'

        return env
