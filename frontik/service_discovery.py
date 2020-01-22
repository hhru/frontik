import logging
import socket

from consul import Check
from consul.aio import Consul

from frontik.options import options
from frontik.version import version

log = logging.getLogger('service_discovery')
client = Consul(host=options.consul_host, port=options.consul_port)
service_name = options.app
__hostname = socket.gethostname()


def _make_service_id() -> str:
    return f'{service_name}-{options.datacenter}-{__hostname}-{options.port}'


service_id = _make_service_id()


async def register_service():
    if not options.consul_enabled:
        log.info('Consul disabled, skipping')
        return None

    http_check = Check.http(
        f'http://{options.consul_check_host}:{options.port}/status',
        f'{options.consul_http_check_interval_sec}s',
        timeout=f'{options.consul_http_check_timeout_sec}s'
    )
    # not supported by version 1.1.0
    meta = {'serviceVersion': version}
    await client.agent.service.register(
        service_name,
        service_id=service_id,
        address=__hostname,
        port=options.port,
        check=http_check,
        tags=options.consul_tags,
    )


async def deregister_service():
    if not options.consul_enabled:
        log.info('Consul disabled, skipping')
        return None
    return client.agent.service.deregister(service_id)
