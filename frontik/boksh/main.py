import asyncio
import logging
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import multiprocess as mp
from pydantic import BaseModel
from tornado.httpserver import HTTPServer

import frontik.boksh

from frontik.app import FrontikApplication
from frontik.boksh.service.aio import AsyncioService, ManagedEnvAsync

from frontik.boksh.service.sync import ProcessService, ManagedEnvSync
from frontik.loggers import MDC, bootstrap_core_logging, _configure_stderr, JSONFormatter
from frontik.options import options
from frontik.server import log


class ListenKafkaService1(AsyncioService):
    def __init__(self, name) -> None:
        super().__init__(name)

    async def run(self):
        self.mark_start_success()
        i = 1
        while not self.is_interrupted():
            await asyncio.sleep(1)
            log.info(f"batch {self.name} {i} log")


class MyFrontikApplication(FrontikApplication):
    def __init__(self, **settings: Any) -> None:
        super().__init__(
            app_root=str(Path(__file__).parent),
            app_module=frontik.boksh.__name__,
            **settings,
        )

        # FrontikAioService.current().add_child("kafka_listener", ListenKafkaService1("loljke").start())
        # FrontikAioService.current().add_child("kafka_listener", ListenKafkaService1("zorzor").start())


class FrontikAioService(AsyncioService):
    # def __init__(self, name: str):
    #     super().__init__(name)

    async def run(self):
        MDC.init(f'master {self.name}')
        options.consul_enabled = False
        options.port = 8080
        options.debug = True
        options.autoreload = True
        options.stderr_log = True
        bootstrap_core_logging("INFO", True, [])
        app = MyFrontikApplication()

        log.info('starting server on %s:%s', options.host, options.port)
        http_server = HTTPServer(app, xheaders=options.xheaders)
        http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
        http_server.start()
        self.mark_start_success()
        log.info('')
        await self.interrupted()
        http_server.stop()


async def run_frontik_server(menv: ManagedEnvAsync):
    MDC.init(f'master')
    options.consul_enabled = False
    options.port = 8080
    options.debug = True
    options.autoreload = True
    options.stderr_log = True
    bootstrap_core_logging("INFO", True, [])
    app = MyFrontikApplication()

    log.info('starting server on %s:%s', options.host, options.port)
    http_server = HTTPServer(app, xheaders=options.xheaders)
    http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
    http_server.start()
    menv.mark_started()
    await menv.interrupted()
    http_server.stop()


class NewUpstreamInfo(BaseModel):
    upstream: str


def notifier(menv: ManagedEnvSync):
    menv.mark_started()
    while not menv.is_interrupted():
        menv.send_message_out(NewUpstreamInfo(upstream="test"))
        time.sleep(1)
    print("stopped")


def main(main_env: ManagedEnvSync):
    while not main_env.is_interrupted():

        time.sleep(1)
    print("exit")


if __name__ == '__main__':
    options.stderr_log = True
    bootstrap_core_logging("INFO", True, [])
    # for handlr in _configure_stderr(JSONFormatter()):
    #     logging.root.addHandler(handlr)

    logger = logging.getLogger(__file__)
    logger.error("qqqqqqqqqqqqqq")
    # service = ProcessService.wrap(main).start()
    # service.add_listener(lambda m: print(m))
    # time.sleep(0.4)
    # service.stop()
    # print(service.interrupted())
    # print(service.stopped())
    # service.wait_for(service.stopped())

    # service = ProcessService.wrap_async(AsyncioService.wrap(run_frontik_server))
    #
    # service.start()
    # print(service.started())
    # service.wait_for(service.started(), timeout=timedelta(milliseconds=1))
    # print(service.started())
    # print("wait stop")
    # service.wait_for(service.stopped())
    # print("stoped")

    # service.add_listener(lambda message: print(message))
