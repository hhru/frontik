from tornado.options import options

try:
    from aioinflux import InfluxDBClient
    has_influx = True
except Exception:
    has_influx = False


def bootstrap_logger(app):
    if not has_influx or options.influxdb_host is None or options.influxdb_port is None:
        return lambda *args: None

    influxdb_client = InfluxDBClient(options.influxdb_host, options.influxdb_port)
    app.influxdb_client = influxdb_client

    def logger_initializer(handler):
        handler.influxdb_client = influxdb_client

    return logger_initializer
