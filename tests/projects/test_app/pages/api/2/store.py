import gzip
import json

from frontik.handler import PageHandler, get_current_handler
from frontik.routing import router


class Page(PageHandler):
    exceptions = []


@router.post('/api/2/envelope/', cls=Page)
async def post_page(handler: Page = get_current_handler()):
    messages = gzip.decompress(handler.request.body).decode('utf8')

    for message in messages.split('\n'):
        if message == '':
            continue
        sentry_event = json.loads(message)
        Page.exceptions.append(sentry_event)


@router.get('/api/2/envelope/', cls=Page)
async def get_page(handler=get_current_handler()):
    handler.json.put({'exceptions': Page.exceptions})


@router.delete('/api/2/envelope/', cls=Page)
async def delete_page():
    Page.exceptions = []
