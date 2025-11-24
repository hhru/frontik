import asyncio
import http.client
from typing import Optional

import pytest
from fastapi import Request
from http_client.request_response import (
    DEADLINE_TIMEOUT_MS_HEADER,
    INSUFFICIENT_TIMEOUT,
    OUTER_TIMEOUT_MS_HEADER,
    SERVER_TIMEOUT,
    RequestResult,
)

from frontik.app import FrontikApplication
from frontik.dependencies import HttpClient
from frontik.routing import router
from frontik.testing import FrontikTestBase
from tests import find_free_port
from tests.instances import frontik_balancer_app, frontik_broken_balancer_app


class TestHttpError:
    free_port = None

    def setup_method(self) -> None:
        frontik_balancer_app.start()
        frontik_broken_balancer_app.start()
        self.free_port = find_free_port(from_port=10000, to_port=20000)

    def make_url(self, url: str) -> str:
        return (
            f'{url}?normal={frontik_balancer_app.port}&broken={frontik_broken_balancer_app.port}&free={self.free_port}'
        )

    def test_retry_connect(self):
        result = frontik_balancer_app.get_page(self.make_url('/retry_connect'))
        assert result.status_code == 200
        assert result.content == b'"resultresultresult"'

    def test_retry_connect_timeout(self):
        result = frontik_balancer_app.get_page(self.make_url('/retry_connect_timeout'))
        assert result.status_code == 200
        assert result.content == b'"resultresultresult"'

    def test_retry_error(self):
        result = frontik_balancer_app.get_page(self.make_url('/retry_error'))
        assert result.status_code == 200
        assert result.content == b'"resultresultresult"'

    def test_no_retry_error(self):
        result = frontik_balancer_app.get_page(self.make_url('/no_retry_error'))
        assert result.status_code == 200
        assert result.content == b'"no retry error"'

    def test_no_retry_timeout(self):
        result = frontik_balancer_app.get_page(self.make_url('/no_retry_timeout'))
        assert result.status_code == 200
        assert result.content == b'"no retry timeout"'

    def test_no_available_backend(self):
        result = frontik_balancer_app.get_page(self.make_url('/no_available_backend'))
        assert result.status_code == 200
        assert result.content == b'"no backend available"'

    def test_retry_on_timeout(self):
        result = frontik_balancer_app.get_page(self.make_url('/retry_on_timeout'))
        assert result.status_code == 200
        assert result.content == b'"result"'

    def test_retry_non_idempotent(self):
        result = frontik_balancer_app.get_page(self.make_url('/retry_non_idempotent_503'))
        assert result.status_code == 200
        assert result.content == b'"result"'

    def test_requests_count(self):
        result = frontik_balancer_app.get_page(self.make_url('/requests_count'))
        assert result.status_code == 200, result.content
        assert result.content == b'"3"'

    def test_slow_start(self):
        result = frontik_balancer_app.get_page(self.make_url('/slow_start'))
        assert result.status_code == 200
        assert result.content == b'"6"'

    def test_retry_count_limit(self):
        result = frontik_balancer_app.get_page(self.make_url('/retry_count_limit'))
        assert result.status_code == 200
        assert result.content == b'"1"'

    def test_speculative_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('/speculative_retry'))
        assert result.status_code == 200
        assert result.content == b'"result"'

    def test_speculative_no_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('/speculative_no_retry'))
        assert result.status_code == 200
        assert result.content == b'"no retry"'

    def test_upstream_profile_with_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('/profile_with_retry'))
        assert result.status_code == 200
        assert result.content == b'"result"'

    def test_upstream_profile_without_retry(self):
        result = frontik_balancer_app.get_page(self.make_url('/profile_without_retry'))
        assert result.status_code == 200
        assert result.content == b'"no retry"'


@router.get('/balancing_headers')
async def balancing_headers(
    request: Request, http_client: HttpClient, sleep_ms: Optional[int] = None
) -> dict[str, str]:
    if sleep_ms is not None:
        await asyncio.sleep(sleep_ms / 1000)
    result: RequestResult[dict[str, str]] = await http_client.post_url(
        request.headers.get('host'), '/balancing_headers', request_timeout=1.3
    )
    assert result.data is not None
    return result.data


@router.post('/balancing_headers')
async def balancing_headers_post(request: Request) -> dict[str, str]:
    return dict(request.headers.items())


class TestBalancingHeaders(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_balancing_headers(self) -> None:
        response: RequestResult[dict[str, str]] = await self.fetch('/balancing_headers')
        assert response.status_code == 200
        assert response.data is not None
        assert float(response.data['x-outer-timeout-ms']) == 1300
        assert float(response.data['x-deadline-timeout-ms']) == 1300

        response = await self.fetch(
            '/balancing_headers',
            headers={OUTER_TIMEOUT_MS_HEADER: '1200', DEADLINE_TIMEOUT_MS_HEADER: '1200'},
        )
        assert response.data is not None
        assert float(response.data['x-outer-timeout-ms']) == 1300  # because outer from request_timeout
        assert 1195 < float(response.data['x-deadline-timeout-ms']) <= 1200

        response = await self.fetch(
            '/balancing_headers?sleep_ms=100',
            headers={OUTER_TIMEOUT_MS_HEADER: '1200', DEADLINE_TIMEOUT_MS_HEADER: '800'},
        )
        assert response.data is not None
        assert float(response.data['x-outer-timeout-ms']) == 1300
        assert 695 < float(response.data['x-deadline-timeout-ms']) <= 700


@router.get('/balancing_statuses')
async def balancing_statuses(request: Request, http_client: HttpClient, *, fail_fast: Optional[bool] = False) -> int:
    result = await http_client.post_url(
        request.headers.get('host'), '/balancing_statuses', request_timeout=0.1, fail_fast=fail_fast
    )
    return result.status_code


@router.post('/balancing_statuses')
async def balancing_statuses_post(request: Request) -> dict[str, str]:
    await asyncio.sleep(2)
    return dict(request.headers.items())


class TestBalancingStatuses(FrontikTestBase):
    @pytest.fixture(scope='class')
    def frontik_app(self) -> FrontikApplication:
        return FrontikApplication(app_module_name=None)

    async def test_balancing_statuses(self) -> None:
        response = await self.fetch('/balancing_statuses')
        assert response.data == SERVER_TIMEOUT

        response = await self.fetch(
            '/balancing_statuses', headers={OUTER_TIMEOUT_MS_HEADER: '1200', DEADLINE_TIMEOUT_MS_HEADER: '5'}
        )
        assert response.data == INSUFFICIENT_TIMEOUT

        response = await self.fetch('/balancing_statuses?fail_fast=true')
        assert response.status_code == http.client.GATEWAY_TIMEOUT

        response = await self.fetch(
            '/balancing_statuses?fail_fast=true',
            headers={OUTER_TIMEOUT_MS_HEADER: '1200', DEADLINE_TIMEOUT_MS_HEADER: '5'},
        )
        assert response.status_code == INSUFFICIENT_TIMEOUT
