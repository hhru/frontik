import logging.handlers
from dataclasses import dataclass, field, fields
from typing import Optional

LOG_DIR_OPTION_NAME = 'log_dir'
STDERR_LOG_OPTION_NAME = 'stderr_log'


DEV_MODE_DEFAULT = 'DEFAULT'
DEV_MODE_DISABLED = 'DISABLED'
DEV_MODE_ON_DEMAND_ROUTING = 'ON_DEMAND_ROUTING'


@dataclass
class Options:
    app_class: Optional[str] = None
    workers: int = 1
    init_workers_timeout_sec: int = 60
    tornado_settings: Optional[dict] = None
    max_active_handlers: int = 100
    reuse_port: bool = True
    xheaders: bool = False
    validate_request_id: bool = False
    xsrf_cookies: bool = False
    max_body_size: int = 100_000_000_000
    openapi_enabled: bool = False

    config: Optional[str] = None
    host: str = '0.0.0.0'
    port: int = 8080
    node_name: str = ''
    common_executor_pool_size: int = 10
    datacenter: Optional[str] = None
    datacenters: list[str] = field(default_factory=list)

    autoreload: bool = False
    dev_mode: str = DEV_MODE_DISABLED
    stop_timeout: int = 3
    asyncio_task_threshold_sec: Optional[float] = None
    asyncio_task_critical_threshold_sec: Optional[float] = None

    log_dir: Optional[str] = None
    log_level: str = 'info'
    update_log_level_interval_in_seconds: int = 300
    log_json: bool = True
    log_write_appender_name: bool = False
    log_text_format: str = '[%(process)s] %(asctime)s %(levelname)s %(name)s: %(message)s'

    stderr_log: bool = False
    stderr_format: str = (
        '%(color)s[%(levelname)1.1s %(asctime)s %(name)s %(module)s:%(lineno)d]%(end_color)s %(message)s'
    )
    stderr_dateformat: str = '%H:%M:%S'

    syslog: bool = False
    syslog_host: str = '127.0.0.1'
    syslog_port: int = logging.handlers.SYSLOG_UDP_PORT
    syslog_tag: str = ''
    syslog_facility: str = 'user'

    suppressed_loggers: list = field(default_factory=list)

    debug: bool = False
    debug_login: Optional[str] = None
    debug_password: Optional[str] = None

    http_client_metrics_kafka_cluster: Optional[str] = None
    http_client_decrease_timeout_by_deadline: Optional[bool] = True

    kafka_clusters: dict = field(default_factory=dict)
    scylla_clusters: dict = field(default_factory=dict)
    scylla_log_level: str = 'warn'
    scylla_retry_policy_logging: bool = False
    scylla_cross_dc_enabled: bool = False
    scylla_metrics_allowed: tuple[str, ...] = (
        'requests_max',
        'requests_percentile_75th',
        'requests_percentile_95th',
        'requests_percentile_99th',
        'errors_connection_timeouts',
        'errors_request_timeouts',
    )
    scylla_metrics_send_stats: bool = True
    scylla_metrics_report_interval: int = 60000

    statsd_host: Optional[str] = None
    statsd_port: Optional[int] = None
    statsd_default_periodic_send_interval_sec: int = 60
    statsd_max_udp_size: Optional[int] = None

    gc_custom_thresholds: Optional[str] = None
    gc_metrics_send_interval_ms: Optional[int] = 1000
    long_gc_log_enabled: bool = False
    long_gc_log_threshold_sec: float = 0.01

    xml_root: Optional[str] = None
    xml_cache_limit: Optional[int] = None
    xml_cache_step: Optional[int] = None
    xsl_root: Optional[str] = None
    xsl_cache_limit: Optional[int] = None
    xsl_cache_step: Optional[int] = None
    xsl_executor_pool_size: int = 1
    jinja_template_root: Optional[str] = None
    jinja_template_cache_limit: int = 50
    jinja_streaming_render_timeout_ms: int = 50

    sentry_dsn: Optional[str] = None
    sentry_max_breadcrumbs: int = 0
    sentry_sample_rate: float = 1.0
    sentry_enable_tracing: Optional[bool] = None
    sentry_traces_sample_rate: Optional[float] = None
    sentry_in_app_include: str = ''
    sentry_exception_integration: bool = False
    sentry_logging_integration: bool = False
    sentry_profiles_sample_rate: Optional[float] = None

    send_timeout_stats_interval_ms: int = 60000

    # consul options
    service_name: Optional[str] = None
    consul_enabled: bool = True
    consul_host: str = '127.0.0.1'
    consul_port: Optional[int] = None
    consul_service_address: Optional[str] = None
    consul_check_host: Optional[str] = None
    consul_http_check_interval_sec: int = 10
    consul_http_check_timeout_sec: float = 1
    consul_tags: list = field(default_factory=list)
    consul_weight_watch_seconds: int = 600
    consul_weight_total_timeout_sec: int = 650
    consul_cache_initial_warmup_timeout_sec: int = 2
    consul_cache_backoff_delay_seconds: int = 10
    consul_consistency_mode: str = 'default'
    consul_weight_consistency_mode: str = 'default'  # options.consul_consistency_mode
    consul_deregister_critical_timeout: str = '120h'

    # upstream options
    upstreams: list = field(default_factory=list)
    cross_datacenter_upstreams: str = ''
    fail_start_on_empty_upstream: bool = True
    skip_empty_upstream_check_for_upstreams: list = field(default_factory=list)

    # opentelemetry options
    opentelemetry_collector_url: str = 'http://127.0.0.1:2360'
    opentelemetry_sampler_ratio: float = 0.01
    opentelemetry_enabled: bool = False
    opentelemetry_exporter_type: str = 'grpc'


options = Options()

ENV_OPTIONS = {
    'node_name': 'NODE_NAME',
}
__available_options = {f.name for f in fields(Options)}
for env in ENV_OPTIONS:
    assert env in __available_options, f'{env} unknown member of Options'


def parse_config_file(path: str) -> None:
    config: dict = {}
    with open(path, 'rb') as config_file:
        exec(config_file.read(), config, config)

    for attr in fields(Options):
        new_value = config.get(attr.name, getattr(options, attr.name))
        if attr.type == int and isinstance(new_value, str):
            new_value = int(new_value)

        setattr(options, attr.name, new_value)
