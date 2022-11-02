import importlib

from examples.example_app.fastapi import application
from frontik.app import FrontikApplication
from frontik.fastapi_integration import frontik_asgi_handler
from frontik.routing import FileMappingRouter


class ExampleFrontikApplication(FrontikApplication):
    def __init__(self, **settings):
        self.fast_api_app = application
        super().__init__(**settings)

    def application_urls(self):
        fastapi_routes = [
            (
                router.path_regex.pattern.replace("$", ".*"),
                frontik_asgi_handler(self.fast_api_app),
            )
            for router in self.fast_api_app.routes
        ]
        return fastapi_routes + [
            ("", FileMappingRouter(importlib.import_module(f"{self.app_module}.pages")))
        ]
