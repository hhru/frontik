import logging.handlers

from tornado.options import define, options as tornado_options

options = tornado_options

define('app', default=None, type=str)
define('app_class', default=None, type=str)
define('workers', default=1, type=int)
define('tornado_settings', default=None, type=dict)
define('max_active_handlers', default=100, type=int)
define('reuse_port', default=True, type=bool)
define('xheaders', default=False, type=bool)

define('config', None, str)
define('host', '0.0.0.0', str)
define('port', 8080, int)
define('common_executor_pool_size', 10, int)

define('autoreload', False, bool)
define('stop_timeout', 3, int)
define('asyncio_task_threshold_sec', None, float)
define('asyncio_task_critical_threshold_sec', None, float)

define('log_dir', default=None, type=str, help='Log file name')
define('log_level', default='info', type=str, help='Log level')
define('log_json', default=True, type=bool, help='Enable JSON logging for files and syslog')
define('log_text_format', default='[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s',
       type=str, help='Log format for files and syslog when JSON logging is disabled')

define('stderr_log', default=False, type=bool, help='Send log output to stderr (colorized if possible).')
define('stderr_format', default='%(color)s[%(levelname)1.1s %(asctime)s %(name)s '
                                '%(module)s:%(lineno)d]%(end_color)s %(message)s', type=str)
define('stderr_dateformat', default='%H:%M:%S', type=str)

define('syslog', default=False, type=bool)
define('syslog_host', default='127.0.0.1', type=str)
define('syslog_port', default=logging.handlers.SYSLOG_UDP_PORT, type=int)
define('syslog_facility', default='user', type=str)

define('suppressed_loggers', default=['tornado.curl_httpclient'], type=list)

define('debug', default=False, type=bool)
define('debug_login', default=None, type=str)
define('debug_password', default=None, type=str)

define('datacenter', default=None, type=str)

define('http_client_default_connect_timeout_sec', default=0.2, type=float)
define('http_client_default_request_timeout_sec', default=2.0, type=float)
define('http_client_default_max_tries', default=2, type=int)
define('http_client_default_max_timeout_tries', default=1, type=int)
define('http_client_default_max_fails', default=0, type=int)
define('http_client_default_fail_timeout_sec', default=10, type=float)
define('http_client_default_retry_policy', default='timeout,http_503', type=str)
define('http_proxy_host', default=None, type=str)
define('http_proxy_port', default=3128, type=int)
define('http_client_allow_cross_datacenter_requests', default=False, type=bool)
define('http_client_metrics_kafka_cluster', default=None, type=str)

define('kafka_clusters', default={}, type=dict)

define('statsd_host', default=None, type=str)
define('statsd_port', default=None, type=int)
define('gc_metrics_send_interval_ms', default=None, type=int)

define('timeout_multiplier', default=1.0, type=float)

define('xml_root', default=None, type=str)
define('xml_cache_limit', default=None, type=int)
define('xml_cache_step', default=None, type=int)
define('xsl_root', default=None, type=str)
define('xsl_cache_limit', default=None, type=int)
define('xsl_cache_step', default=None, type=int)
define('xsl_executor_pool_size', default=1, type=int)
define('jinja_template_root', default=None, type=str)
define('jinja_template_cache_limit', default=50, type=int)
define('jinja_streaming_render_timeout_ms', default=50, type=int)

define('sentry_dsn', default=None, type=str, metavar='http://public:secret@example.com/1')

define('max_http_clients', default=100, type=int)
define('max_http_clients_connects', default=None, type=int)
define('send_timeout_stats_interval_ms', default=60000, type=int)

define('consul_enabled', default=True, type=bool)
define('consul_host', default='127.0.0.1', type=str)
define('consul_port', default=None, type=int)
define('consul_http_check_interval_sec', default=10, type=int)
define('consul_http_check_timeout_sec', default=0.5, type=float)
define('consul_tags', default=[], type=list)
