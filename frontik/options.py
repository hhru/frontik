from dataclasses import dataclass, field, fields
import logging.handlers

LOG_DIR_OPTION_NAME = 'log_dir'
STDERR_LOG_OPTION_NAME = 'stderr_log'


@dataclass
class Options:
    app: str = None
    app_class: str = None
    workers: int = 1
    init_workers_timeout_sec: int = 60
    tornado_settings: dict = None
    max_active_handlers: int = 100
    reuse_port: bool = True
    xheaders: bool = False
    validate_request_id: bool = False

    config: str = None
    host: str = '0.0.0.0'
    port: int = 8080
    node_name: str = ''
    common_executor_pool_size: int = 10

    autoreload: bool = False
    stop_timeout: int = 3
    asyncio_task_threshold_sec: float = None
    asyncio_task_critical_threshold_sec: float = None

    log_dir: str = None
    log_level: str = 'info'
    update_log_level_interval_in_seconds: int = 300
    log_json: bool = True
    log_text_format: str = '[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s'

    stderr_log: bool = False
    stderr_format: str = '%(color)s[%(levelname)1.1s %(asctime)s %(name)s ' \
                         '%(module)s:%(lineno)d]%(end_color)s %(message)s'
    stderr_dateformat: str = '%H:%M:%S'

    syslog: bool = False
    syslog_host: str = '127.0.0.1'
    syslog_port: int = logging.handlers.SYSLOG_UDP_PORT
    syslog_tag: str = ''
    syslog_facility: str = 'user'

    suppressed_loggers: list = field(default_factory=lambda: ['tornado.curl_httpclient'])

    debug: bool = False
    debug_login: str = None
    debug_password: str = None

    http_client_metrics_kafka_cluster: str = None

    kafka_clusters: dict = field(default_factory=lambda: {})

    statsd_host: str = None
    statsd_port: int = None
    statsd_default_periodic_send_interval_sec: int = 60
    gc_metrics_send_interval_ms: int = None
    long_gc_log_enabled: bool = True
    long_gc_log_threshold_sec: float = 0.01

    xml_root: str = None
    xml_cache_limit: int = None
    xml_cache_step: int = None
    xsl_root: str = None
    xsl_cache_limit: int = None
    xsl_cache_step: int = None
    xsl_executor_pool_size: int = 1
    jinja_template_root: str = None
    jinja_template_cache_limit: int = 50
    jinja_streaming_render_timeout_ms: int = 50

    sentry_dsn: str = None
    sentry_connect_timeout_sec: float = 0.2
    sentry_request_timeout_sec: float = 2.0

    max_http_clients: int = 100
    max_http_clients_connects: int = None
    send_timeout_stats_interval_ms: int = 60000

    # consul options
    consul_enabled: bool = True
    consul_host: str = '127.0.0.1'
    consul_port: int = None
    consul_service_address: str = None
    consul_check_host: str = None
    consul_http_check_interval_sec: int = 10
    consul_http_check_timeout_sec: float = 1
    consul_tags: list = field(default_factory=lambda: [])
    consul_weight_watch_seconds: int = 600
    consul_weight_total_timeout_sec: int = 650
    consul_cache_initial_warmup_timeout_sec: int = 2
    consul_cache_backoff_delay_seconds: int = 10
    consul_consistency_mode: str = 'default'
    consul_weight_consistency_mode: str = 'default'  # options.consul_consistency_mode
    consul_deregister_critical_timeout: str = '120h'

    # upstream options
    upstreams: list = field(default_factory=lambda: [])
    fail_start_on_empty_upstream: bool = True

    # opentelemetry options
    opentelemetry_collector_url: str = 'http://127.0.0.1:2360'
    opentelemetry_sampler_ratio: float = 0.01
    opentelemetry_enabled: bool = False


options = Options()


def parse_config_file(path):
    config = {}
    with open(path, 'rb') as config_file:
        exec(config_file.read(), config, config)

    for attr in fields(Options):
        new_value = config.get(attr.name, getattr(options, attr.name))
        if attr.type == int and isinstance(new_value, str):
            new_value = int(new_value)

        setattr(options, attr.name, new_value)
