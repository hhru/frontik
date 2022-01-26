import logging.handlers

from tornado.options import define, options as tornado_options

LOG_DIR_OPTION_NAME = 'log_dir'
STDERR_LOG_OPTION_NAME = 'stderr_log'

options = tornado_options

define('app', default=None, type=str)
define('app_class', default=None, type=str)
define('workers', default=1, type=int)
define('init_workers_timeout_sec', default=60, type=int)
define('tornado_settings', default=None, type=dict)
define('max_active_handlers', default=100, type=int)
define('reuse_port', default=True, type=bool)
define('xheaders', default=False, type=bool)
define('validate_request_id', default=False, type=bool)

define('config', None, str)
define('host', '0.0.0.0', str)
define('port', 8080, int)
if 'node_name' not in options:
    define('node_name', default='', type=str)
define('common_executor_pool_size', 10, int)

define('autoreload', False, bool)
define('stop_timeout', 3, int)
define('asyncio_task_threshold_sec', None, float)
define('asyncio_task_critical_threshold_sec', None, float)

define(LOG_DIR_OPTION_NAME, default=None, type=str, help='Log file name')
define('log_level', default='info', type=str, help='Log level')
define('update_log_level_interval_in_seconds', default=300, type=int)
define('log_json', default=True, type=bool, help='Enable JSON logging for files and syslog')
define('log_text_format', default='[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s',
       type=str, help='Log format for files and syslog when JSON logging is disabled')

define(STDERR_LOG_OPTION_NAME, default=False, type=bool, help='Send log output to stderr (colorized if possible).')
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

define('http_client_metrics_kafka_cluster', default=None, type=str)

define('kafka_clusters', default={}, type=dict)

define('statsd_host', default=None, type=str)
define('statsd_port', default=None, type=int)
define('gc_metrics_send_interval_ms', default=None, type=int)

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
define('sentry_connect_timeout_sec', default=0.2, type=float)
define('sentry_request_timeout_sec', default=2.0, type=float)

define('max_http_clients', default=100, type=int)
define('max_http_clients_connects', default=None, type=int)
define('send_timeout_stats_interval_ms', default=60000, type=int)

# consul options
define('consul_enabled', default=True, type=bool)
define('consul_host', default='127.0.0.1', type=str)
define('consul_port', default=None, type=int)
define('consul_service_address', default=None, type=str)
define('consul_check_host', default=None, type=str)
define('consul_http_check_interval_sec', default=10, type=int)
define('consul_http_check_timeout_sec', default=1, type=float)
define('consul_tags', default=[], type=list)
define('consul_weight_watch_seconds', default=600, type=int)
define('consul_weight_total_timeout_sec', default=650, type=int)
define('consul_cache_initial_warmup_timeout_sec', default=2, type=int)
define('consul_cache_backoff_delay_seconds', default=10, type=int)
define('consul_consistency_mode', default='default', type=str)
define('consul_weight_consistency_mode', default=options.consul_consistency_mode, type=str)
define('consul_deregister_critical_timeout', default='120h', type=str)

# upstream options
define('upstreams', default=[], type=list)
define('fail_start_on_empty_upstream', default=True, type=bool)

# opentelemetry options
define('opentelemetry_collector_url', default='http://127.0.0.1:2360', type=str)
define('opentelemetry_sampler_ratio', default=0.01, type=float)
define('opentelemetry_enabled', default=False, type=bool)
