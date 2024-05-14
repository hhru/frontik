import re

from fastapi import Request

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import regex_router

PERMANENT_REDIRECT_PATTERN = re.compile(r'^/redirect/permanent')
TEMPORARY_REDIRECT_PATTERN = re.compile(r'^/redirect/temporary')


@regex_router.get('^/redirect', cls=PageHandler)
async def get_page(request: Request, handler: PageHandler = get_current_handler()) -> None:
    if PERMANENT_REDIRECT_PATTERN.match(request.url.path):
        permanent = True
    elif TEMPORARY_REDIRECT_PATTERN.match(request.url.path):
        permanent = False
    else:
        raise RuntimeError('123')

    to_url = '/finish?foo=bar'
    if request.url.query:
        to_url = to_url + f'&{request.url.query}'
    handler.redirect(to_url, permanent)
