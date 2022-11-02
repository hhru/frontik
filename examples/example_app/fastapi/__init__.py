import importlib
import pkgutil

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

application = FastAPI(
    on_startup=[

    ],
    on_shutdown=[

    ],
    exception_handlers={

    },
    middleware=[

    ],
)


def custom_openapi(*args):
    openapi_schema = get_openapi(
        title="Custom title",
        version="2.5.0",
        description="This is a very custom OpenAPI schema",
        routes=application.routes,
    )
    openapi_schema["info"]["x-logo"] = {
        "url": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
    }
    application.openapi_schema = openapi_schema
    return application.openapi_schema


application.openapi = custom_openapi


def _import_app_routes(application: FastAPI):
    from . import routes

    for _, module, __ in pkgutil.walk_packages(routes.__path__, prefix=f"{routes.__package__}."):
        imported_module = importlib.import_module(module)
        if hasattr(imported_module, "app_router"):
            application.include_router(imported_module.app_router)
            # LOGGER.info(f"imported app_router from {module}")


_import_app_routes(application)
