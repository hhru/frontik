import asyncio
import multiprocessing as mp
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from tornado.httpserver import HTTPServer

import frontik.boksh
from frontik.app import FrontikApplication
from frontik.boksh.service import AsyncioService, ProcessService, ThreadService, ManagedEnv
from frontik.loggers import MDC, bootstrap_core_logging
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


class TestProcessService(ProcessService):
    def __init__(self, name: str, all_workers_on: mp.Event) -> None:
        super().__init__(name)
        self.all_workers_on = all_workers_on

    def run(self):
        print("before start")
        while True:
            print("wait")
            time.sleep(1)
            # result = self.in_queue.get()
            # print(result)

            # print(f"{self.name} {self.all_workers_on}")
            # time.sleep(1)
            # i += 1
            # print(mp.current_process() == self._process)
        # print("interrupted")
        # print("stopped")


async def frontik_lifespan(menv: ManagedEnv):
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
    http_server.stop()


class NewUpstreamInfo(BaseModel):
    upstream: str


def notifier(menv: ManagedEnv):
    menv.mark_started()
    print("started")
    while not menv.is_interrupted():
        menv.send_message_out(NewUpstreamInfo(upstream="test"))
        time.sleep(1)
    print("stopped")


if __name__ == '__main__':

    service = ProcessService.wrap_async(AsyncioService.wrap(frontik_lifespan))
    service.start()
    # service.add_listener(lambda message: print(message))
    service.wait_for(service.started())
    service.stop()
    print("wait stop")
    # time.sleep(5)

    service.wait_for(service.stopped())
