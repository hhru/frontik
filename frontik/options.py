# coding=utf-8

import tornado.options

tornado.options.define('urls', default=[], type=list)
tornado.options.define('app', default=None, type=str)
tornado.options.define('tornado_settings', default=None, type=dict)
tornado.options.define('handlers_count', default=100, type=int)

tornado.options.define('logfile', default=None, type=str, help='log file name')
tornado.options.define('loglevel', default='info', type=str, help='log level')
tornado.options.define('logformat', default='[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s', type=str)
tornado.options.define('stdoutformat', default='%(color)s[%(levelname)1.1s %(asctime)s %(name)s '
                                               '%(module)s:%(lineno)d]%(end_color)s %(message)s', type=str)
tornado.options.define('stdoutdateformat', default='%y.%m.%d %H:%M:%S', type=str)
tornado.options.define('suppressed_loggers', default=['tornado.curl_httpclient'], type=list)

tornado.options.define('timings_log_enabled', default=False, type=bool)
tornado.options.define('timings_log_file_postfix', default='timings', type=str)
tornado.options.define('timings_log_message_format', default='Timings for %(page)s : %(stages)s', type=str)

tornado.options.define('syslog_address', default='/dev/log', type=str)
tornado.options.define('syslog', default=False, type=bool)
tornado.options.define('syslog_facility', default='user', type=str)
tornado.options.define('syslog_msg_max_length', default=2048, type=int)

tornado.options.define('debug', default=False, type=bool)
tornado.options.define('debug_login', default=None, type=str)
tornado.options.define('debug_password', default=None, type=str)

tornado.options.define('timeout_multiplier', default=1.0, type=float)
tornado.options.define('long_request_timeout', default=None, type=float)
tornado.options.define('kill_long_requests', default=False, type=bool)

tornado.options.define('xsl_executor', default='threaded', type=str, metavar='threaded|ioloop')
tornado.options.define('json_executor', default='ioloop', type=str, metavar='threaded|ioloop')
tornado.options.define('executor_pool_size', default=1, type=int)
tornado.options.define('warn_no_jobs', default=True, type=bool)

tornado.options.define('graylog', default=False, type=bool)
tornado.options.define('graylog_host', default='localhost', type=str)
tornado.options.define('graylog_port', default=12201, type=int)
