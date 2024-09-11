import gzip
import json

from fastapi import Request

from frontik.routing import router


# add `sentry_dsn = 'http://secret@127.0.0.1:9400/2'` to .cfg
@router.post('/api/2/envelope/')
async def sentry_envelope(request: Request) -> None:
    body = await request.body()
    message = gzip.decompress(body).decode('utf8')
    sentry_event = json.loads(message.split('\n')[-1])
    print(sentry_event)  # noqa
