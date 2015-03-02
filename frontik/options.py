# coding=utf-8

import tornado.options

tornado.options.define('app', default=None, type=str)
tornado.options.define('app_class', default=None, type=str)
tornado.options.define('app_root_url', default='/', type=str)
tornado.options.define('tornado_settings', default=None, type=dict)
tornado.options.define('handlers_count', default=100, type=int)

tornado.options.define('loglevel', default='info', type=str, help='Log level')
tornado.options.define('logformat', default='[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s', type=str,
                       help='Log format for files and syslog')
tornado.options.define('logfile', default=None, type=str, help='Log file name')

tornado.options.define('stderr_log', default=False, type=bool,
                       help='Send log output to stderr (colorized if possible).')
tornado.options.define('stderr_format', default='%(color)s[%(levelname)1.1s %(asctime)s %(name)s '
                                                '%(module)s:%(lineno)d]%(end_color)s %(message)s', type=str)
tornado.options.define('stderr_dateformat', default='%y.%m.%d %H:%M:%S', type=str)

tornado.options.define('syslog', default=False, type=bool)
tornado.options.define('syslog_address', default='/dev/log', type=str)
tornado.options.define('syslog_facility', default='user', type=str)

tornado.options.define('suppressed_loggers', default=['tornado.curl_httpclient'], type=list)

tornado.options.define('debug', default=False, type=bool)
tornado.options.define('debug_login', default=None, type=str)
tornado.options.define('debug_password', default=None, type=str)

tornado.options.define('http_client_default_connect_timeout', default=0.2, type=float)
tornado.options.define('http_client_default_request_timeout', default=2.0, type=float)
tornado.options.define('timeout_multiplier', default=1.0, type=float)
tornado.options.define('long_request_timeout', default=None, type=float)
tornado.options.define('kill_long_requests', default=False, type=bool)

tornado.options.define('xsl_executor', default='threaded', type=str, metavar='threaded|ioloop')
tornado.options.define('json_executor', default='ioloop', type=str, metavar='threaded|ioloop')
tornado.options.define('executor_pool_size', default=1, type=int)
tornado.options.define('warn_no_jobs', default=True, type=bool)

tornado.options.define('xml_root', default=None, type=str)
tornado.options.define('xml_cache_limit', default=None, type=int)
tornado.options.define('xml_cache_step', default=None, type=int)
tornado.options.define('xsl_root', default=None, type=str)
tornado.options.define('xsl_cache_limit', default=None, type=int)
tornado.options.define('xsl_cache_step', default=None, type=int)
tornado.options.define('template_root', default=None, type=str)
tornado.options.define('template_cache_limit', default=50, type=int)
tornado.options.define('debug_labels', default=None, type=dict)

tornado.options.define('graylog', default=False, type=bool)
tornado.options.define('graylog_host', default='localhost', type=str)
tornado.options.define('graylog_port', default=12201, type=int)
