import tornado.options

tornado.options.define('apps', {}, dict)
tornado.options.define('urls', [], list)
tornado.options.define('suppressed_loggers', ['tornado.curl_httpclient'], list)
tornado.options.define('handlers_count', 100, int)

tornado.options.define('logformat', '[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s', str)
tornado.options.define('syslog_address', "/dev/log", str)
tornado.options.define('syslog', False, bool)
tornado.options.define('syslog_facility', 'user', str)
tornado.options.define('syslog_msg_max_length', 2048, int)

tornado.options.define('xml_debug', False, bool)
tornado.options.define('debug', False, bool)
tornado.options.define('debug_login', None, str)
tornado.options.define('debug_password', None, str)
tornado.options.define('debug_xsl', '/usr/lib/frontik/debug.xsl', str)

tornado.options.define('timeout_multiplier', 1.0, float)
tornado.options.define('long_request_timeout', None, float)
tornado.options.define('kill_long_requests', False, bool)

tornado.options.define('executor_pool_size', 1, int)

tornado.options.define('graylog', False, bool)
tornado.options.define('graylog_host', "localhost", str)
tornado.options.define('graylog_port', 12201, int)

tornado.options.define('warn_no_jobs', True, bool)
