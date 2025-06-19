import http.client

from http_client.request_response import INSUFFICIENT_TIMEOUT, SERVER_TIMEOUT

CLIENT_CLOSED_REQUEST = 499
NON_CRITICAL_BAD_GATEWAY = 569
ALLOWED_STATUSES = {*http.client.responses.keys(), CLIENT_CLOSED_REQUEST, NON_CRITICAL_BAD_GATEWAY}

HTTP_REASON = {
    **http.client.responses,
    SERVER_TIMEOUT: 'Server Timeout',
    INSUFFICIENT_TIMEOUT: 'Insufficient Timeout',
}
