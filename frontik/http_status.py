import http.client

NON_CRITICAL_BAD_GATEWAY = 569
ALLOWED_STATUSES = list(http.client.responses.keys()) + [NON_CRITICAL_BAD_GATEWAY]
