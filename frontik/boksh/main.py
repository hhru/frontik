import asyncio
import multiprocessing
import queue
import random
import time
from pathlib import Path
from typing import Any, Callable

import multiprocess as mp
from pydantic import BaseModel
from tornado.httpserver import HTTPServer

import frontik.boksh
from frontik.app import FrontikApplication
from frontik.boksh.service.aio import AsyncioService, AsyncManagedEnv
from frontik.boksh.service.common import Service
from frontik.boksh.service.sync import ProcessService, ManagedEnvSync, ThreadService
from frontik.loggers import MDC, bootstrap_core_logging
from frontik.options import options
from frontik.server import log


class MyFrontikApplication(FrontikApplication):
    def __init__(self, **settings: Any) -> None:
        super().__init__(
            app_root=str(Path(__file__).parent),
            app_module=frontik.boksh.__name__,
            # is_started_check=is_started_check,
            **settings,
        )


def make_frontik(is_started_check: Callable[[], bool]):
    async def run_frontik_server(menv: AsyncManagedEnv):
        MDC.init(f'master')
        options.consul_enabled = False
        options.port = 8080
        # options.debug = True
        # options.autoreload = True
        options.stderr_log = True
        bootstrap_core_logging("INFO", True, [])
        app = MyFrontikApplication(is_started_check=is_started_check)
        menv.add_message_handler(lambda m: print(m))

        log.info('starting server on %s:%s', options.host, options.port)
        http_server = HTTPServer(app, xheaders=options.xheaders)
        http_server.bind(options.port, options.host, reuse_port=options.reuse_port)
        http_server.start()
        menv.mark_started()
        await menv.interrupted()
        http_server.stop()

    return run_frontik_server


class NewUpstreamInfo(BaseModel):
    upstream: str


def notifier(menv: ManagedEnvSync):
    menv.mark_started()
    while not menv.is_interrupted():
        menv.send_message_out(NewUpstreamInfo(upstream="test"))
        time.sleep(1)
    print("stopped")






# def concurrent_thread(env: ):



if __name__ == '__main__':
    services = []
    queue = multiprocessing.JoinableQueue()

    def listeners(main_env: ManagedEnvSync):
        while not main_env.is_interrupted():
            msg = queue.get()
            # print(f"{id(Service.current())} got message {msg}")
            queue.task_done()

    def producers(main_env: ManagedEnvSync):
        while not main_env.is_interrupted():
            time.sleep(random.randint(3, 10))
            queue.put_nowait(f"from {id(Service.current())}")


    # for i in range(1):
    #     services.append(ThreadService.wrap(listeners).start())
    # # #
    # for i in range(1):
    #     services.append(ThreadService.wrap(producers).start())

    # time.sleep(20)
    # init_workers_count_down = multiprocessing.Value('i', options.workers)
    # event = multiprocessing.Event()
    async def main():
        service = AsyncioService.wrap(make_frontik(lambda: True)).start()
        print(id(service))
        await service.wait_for(service.stopped())
    #
    asyncio.run(main())
    # service.start()
    # time.sleep(5)
    # event.set()
    # print("started")
    #
    # service.wait_for(service.stopped())

    # asyncio.run(main())

    # service = ProcessService.wrap_async(AsyncioService.wrap(run_frontik_server))
    # ProcessService.wrap_async(AsyncioService.wrap(run_frontik_server))
    #
    # service.start()
    # print(service.started())
    # service.wait_for(service.started(), timeout=timedelta(milliseconds=1))
    # print(service.started())
    # print("wait stop")
    # service.wait_for(service.stopped())
    # print("stoped")

    # service.add_listener(lambda message: print(message))

    # options.stderr_log = True
    # logging.root.setLevel(logging.NOTSET)
    # bootstrap_core_logging("INFO", True, [])
    # for handlr in _configure_stderr(JSONFormatter()):
    #     logging.root.addHandler(handlr)

    # logger = logging.getLogger(__file__)
    # logger.info("qqqqqqqqqqqqqq")
    # service = ProcessService.wrap(main).start()
    # service.add_listener(lambda m: print(m))
    # time.sleep(0.4)
    # service.stop()
    # print(service.interrupted())
    # print(service.stopped())
    # service.wait_for(service.stopped())
    # async def main():
