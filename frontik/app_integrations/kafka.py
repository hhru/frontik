from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Optional

from aiokafka import AIOKafkaProducer
from http_client.balancing import Upstream
from tornado import gen

from frontik.app_integrations import Integration
from frontik.options import options

if TYPE_CHECKING:
    from asyncio import Future

    from frontik.app import FrontikApplication


class KafkaIntegration(Integration):
    def __init__(self):
        self.kafka_producers = {}

    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        def get_kafka_producer(producer_name: str) -> Optional[AIOKafkaProducer]:
            return self.kafka_producers.get(producer_name)

        app.get_kafka_producer = get_kafka_producer  # type: ignore

        if options.kafka_clusters:
            init_futures = []
            upstreams = app.service_discovery.get_upstreams_copy()

            for cluster_name, producer_settings in options.kafka_clusters.items():
                if producer_settings:
                    upstream: Upstream = upstreams.get('kafka-' + cluster_name)
                    bootstrap_servers = ','.join(server.address for server in upstream.servers if server is not None)
                    producer_settings['bootstrap_servers'] = bootstrap_servers
                    producer = AIOKafkaProducer(loop=asyncio.get_event_loop(), **producer_settings)
                    self.kafka_producers[cluster_name] = producer
                    init_futures.append(asyncio.ensure_future(producer.start()))

            return gen.multi(init_futures)

        return None

    def initialize_handler(self, handler):
        handler.get_kafka_producer = handler.application.get_kafka_producer
