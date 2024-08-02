import jinja2

from frontik.app import FrontikApplication
from frontik.options import options
from frontik.util import get_abs_path


class TestApplication(FrontikApplication):
    def get_jinja_environment(self):
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(get_abs_path(self.app_root, options.jinja_template_root)),
        )

        env.globals['custom_env_function'] = lambda: 'custom_env_function_value'

        return env
