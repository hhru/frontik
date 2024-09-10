from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Any
import time
import asyncio
import starlette.middleware.base

from frontik.json_builder import JsonBuilder
from frontik.producers.asgi_json_producer import JsonProducer
from frontik.options import options
import jinja2
from frontik.util import get_abs_path


class ProducersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, app_root: str):
        super().__init__(app)
        if options.jinja_template_root is not None:
            self.jinja_environment = jinja2.Environment(
                auto_reload=options.debug,
                cache_size=options.jinja_template_cache_limit,
                loader=jinja2.FileSystemLoader(get_abs_path(app_root, options.jinja_template_root)),
            )
        else:
            self.jinja_environment = None

    async def dispatch(self, request: Request, call_next):
        request.state.json_producer = JsonProducer(
            debug_mode=request['debug_mode'],
            jinja_environment=self.jinja_environment,
        )

        # response: starlette.middleware.base._StreamingResponse = await call_next(request)
        response: Response = await call_next(request)

        if not request.state.json_producer.json.is_empty():
            # какойто бы еще чек, что ретурна не было
            content, media_type = await request.state.json_producer.render()
            response = Response(
                content=content,
                status_code=response.status_code,
                headers=response.headers,
                media_type=media_type
            )

        return response
