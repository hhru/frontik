import re

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import regex_router

PERMANENT_REDIRECT_PATTERN = re.compile(r'^/redirect/permanent')
TEMPORARY_REDIRECT_PATTERN = re.compile(r'^/redirect/temporary')


@regex_router.get('^/redirect', cls=PageHandler)
async def get_page(handler: PageHandler = get_current_handler()) -> None:
    if PERMANENT_REDIRECT_PATTERN.match(handler.path):
        permanent = True
    elif TEMPORARY_REDIRECT_PATTERN.match(handler.path):
        permanent = False
    else:
        raise RuntimeError('123')

    to_url = '/finish?foo=bar'
    if handler.request.query:
        to_url = to_url + f'&{handler.request.query}'
    handler.redirect(to_url, permanent)
