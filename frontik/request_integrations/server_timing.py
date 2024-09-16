from contextlib import contextmanager

from frontik.request_integrations.integrations_dto import IntegrationDto


@contextmanager
def server_timing(_, tornado_request):
    dto = IntegrationDto()
    yield dto
    if dto.response is not None:
        dto.response.headers.add(
            'Server-Timing', f'frontik;desc="frontik execution time";dur={tornado_request.request_time()!s}'
        )
