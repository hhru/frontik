import http.client

CLIENT_CLOSED_REQUEST = 499
NON_CRITICAL_BAD_GATEWAY = 569
ALLOWED_STATUSES = {*http.client.responses.keys(), CLIENT_CLOSED_REQUEST, NON_CRITICAL_BAD_GATEWAY}
