from aiohttp.client import ClientTimeout
from aioinflux import InfluxDBClient

from frontik.integrations import Integration, integrations_logger
from frontik.options import options


class InfluxdbIntegration(Integration):
    def __init__(self):
        self.influxdb_client = None

    def initialize_app(self, app):
        if options.influxdb_host is None or options.influxdb_port is None:
            integrations_logger.info(
                'influxdb integration is disabled: influxdb_host / influxdb_port options are not configured'
            )
            return

        self.influxdb_client = InfluxDBClient(options.influxdb_host, options.influxdb_port)
        self.influxdb_client._session._timeout = ClientTimeout(
            connect=options.influxdb_connect_timeout,
            total=options.influxdb_request_timeout
        )

        app.influxdb_client = self.influxdb_client

    def initialize_handler(self, handler):
        handler.influxdb_client = self.influxdb_client
