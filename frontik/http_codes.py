# coding=utf-8

from frontik.compat import PY3

if PY3:
    import http.client as httpcodes
else:
    import httplib as httpcodes

OK = int(httpcodes.OK)
SERVICE_UNAVAILABLE = int(httpcodes.SERVICE_UNAVAILABLE)
UNAUTHORIZED = int(httpcodes.UNAUTHORIZED)

# Additional HTTP Status Codes according to http://tools.ietf.org/html/rfc6585 (for Python 2)

PRECONDITION_REQUIRED = 428
TOO_MANY_REQUESTS = 429
REQUEST_HEADER_FIELDS_TOO_LARGE = 431
NETWORK_AUTHENTICATION_REQUIRED = 511

_additional_response_codes = {
    PRECONDITION_REQUIRED: 'Precondition Required',
    TOO_MANY_REQUESTS: 'Too Many Requests',
    REQUEST_HEADER_FIELDS_TOO_LARGE: 'Request Header Fields Too Large',
    NETWORK_AUTHENTICATION_REQUIRED: 'Network Authentication Required',
}


def process_status_code(status_code, reason=None):
    if status_code not in httpcodes.responses:
        if status_code in _additional_response_codes:
            # autoset reason for extended HTTP codes
            reason = reason if reason is not None else _additional_response_codes[status_code]
        else:
            # change error code for unknown HTTP codes (ex. fake 599 error code)
            status_code = SERVICE_UNAVAILABLE

    return status_code, reason
