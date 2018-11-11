import time
import logging
from collections import namedtuple

from tornado.httputil import url_concat

Error = namedtuple('Error', 'error,code,reason')

protobuf_logger = logging.getLogger('frontik.protobuf_client')


class RpcController(object):
    def __init__(self):
        self.Reset()

    def Reset(self):
        self.fail_reason = None
        self.canceled = False
        self.failed = False

    def StartCancel(self):
        self.canceled = True

    def IsCanceled(self):
        return self.canceled

    def SetFailed(self, reason):
        self.failed = True
        self.fail_reason = reason

    def ErrorText(self):
        return self.fail_reason

    def Failed(self):
        return self.failed


class RpcChannel(object):
    CONTENT_TYPE_HEADER = 'Content-Type'
    PROTOBUF_CONTENT_TYPE = 'application/x-protobuf'

    def __init__(self, post_url, host, query_params=None, **kwargs):
        self.host = host
        self.post_url = post_url
        self.query_params = query_params if query_params is not None else {}
        self.kwargs = kwargs

    def CallMethod(self, method_descriptor, rpc_controller, request, response_class, done):
        url = '/{service}/{method}'.format(
            service=method_descriptor.containing_service.name, method=method_descriptor.name
        )

        def _cb(_, response):
            decode_start_time = time.time()

            rc = response_class()
            try:
                rc.ParseFromString(response.body)
            except Exception as e:
                _error_no_proto_msg(response.body, response.headers, str(e), response.code)
                return

            if response.error is not None or rpc_controller.IsCanceled():
                _error(rc, response.headers, response.error, response.code)
                return

            response_content_type = response.headers.get(RpcChannel.CONTENT_TYPE_HEADER)
            if response_content_type != response.request.headers.get(RpcChannel.CONTENT_TYPE_HEADER):
                protobuf_logger.warn('Wrong Content-Type in response: %s', response_content_type)

            protobuf_logger.info(
                'Decoded protobuf response from %s in %.2fms',
                response.request.url, (time.time() - decode_start_time) * 1000,
                extra={'_protobuf': rc}
            )

            done(rc)

        def _error(response, headers, error=None, code=None):
            fail_reason = 'RPC fail: ' + _compose_reason(headers, error) + '\n response is:\n' + str(response)
            rpc_controller.SetFailed(Error(error, code, fail_reason))
            done(None)

        def _error_no_proto_msg(msg, headers, error, code):
            reason_header = 'RPC fail: ' + _compose_reason(headers, error)

            try:
                fail_reason = reason_header + ('\nmessage is:\n' + str(msg) if msg is not None else '')
                error_data = Error(error, code, fail_reason)
            except ValueError:
                fail_reason = reason_header + "\nCan't show message"
                error_data = Error(error, code, fail_reason)

            rpc_controller.SetFailed(error_data)
            done(None)

        def _compose_reason(_, error):
            fail_reason = ''

            if error is not None:
                fail_reason += str(error)

            if rpc_controller.IsCanceled():
                fail_reason += 'Call was canceled by client'

            if fail_reason == '':
                fail_reason = 'Unknown fail!'

            return fail_reason

        rpc_controller.Reset()

        encode_start_time = time.time()
        payload = request.SerializeToString()

        protobuf_logger.info(
            'Encoded protobuf request to %s %s in %.2fms',
            self.host, url, (time.time() - encode_start_time) * 1000,
            extra={'_protobuf': request}
        )

        self.post_url(self.host, url_concat(url, self.query_params), data=payload,
                      content_type=RpcChannel.PROTOBUF_CONTENT_TYPE,
                      callback=_cb,
                      **self.kwargs)
