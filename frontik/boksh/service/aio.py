import asyncio
import inspect
import logging
import multiprocessing
from abc import abstractmethod
from typing import Callable, Self, Type, Coroutine, Protocol, Any

from frontik.boksh.service.common import (
    Service,
    start_all_children,
    ServiceState,
    stop_all_children,
    proxy_message_to_all_children,
)
from frontik.boksh.service.timeout import ServiceTimeout, timeout_seconds

logger = logging.Logger(__file__)


class AsyncioService(Service[asyncio.Future]):
    def __init__(self, address: str | None = None):
        super().__init__(address)
        self._state = ServiceState.NOT_STARTED
        self._main_task: asyncio.Task | None = None

        # in-out messaging
        self._in_queue_processing_task: asyncio.Task | None = None
        self._out_queue_processing_task: asyncio.Task | None = None
        self._in_queue: asyncio.Queue = asyncio.Queue()
        self._out_queue: asyncio.Queue = asyncio.Queue()

        self.on_start_callbacks: list[Callable[[Self], ...]] = [
            start_all_children,
        ]

    def get_state(self) -> ServiceState:
        return self._state

    def add_on_start_callback(self, callback: Callable[['AsyncioService'], ...]) -> Self:
        self.on_start_callbacks.append(callback)
        return self

    def send_message(self, message: Any):
        self._main_task.get_loop().call_soon_threadsafe(lambda: self._in_queue.put_nowait(message))

    def _send_message_out(self, message: Any):
        self._main_task.get_loop().call_soon_threadsafe(lambda: self._out_queue.put_nowait(message))

    def _add_message_handler(self, message_hadler: Callable[[Any], ...]):
        self.in_message_handlers.append(message_hadler)

    def add_message_listener(self, message_listener: Callable[[Any], ...]) -> Self:
        self.out_message_listeners.append(message_listener)
        return self

    def start(self):
        logger.info(f"starting service {self}")
        if self.get_state() != ServiceState.NOT_STARTED:
            return
        self._state = ServiceState.STARTING

        self._started = asyncio.Future()
        self._interrupted = asyncio.Future()
        self._stopped = asyncio.Future()

        for cb in self.on_start_callbacks:
            cb(self)

        def _start_queues_processing_tasks(future: asyncio.Future):
            if future.exception():
                return
            self._in_queue_processing_task = queue_messages_processing_task(
                self._in_queue,
                self.in_message_handlers,
            )
            self._out_queue_processing_task = queue_messages_processing_task(
                self._out_queue,
                self.out_message_listeners,
            )

        self._started.add_done_callback(_start_queues_processing_tasks)

        self._main_task = asyncio.create_task(self.__run_wrapper())
        return self

    def _mark_started(self):
        if not self._started.done():
            self._started.set_result(None)
            self._state = ServiceState.STARTED

    def stop(self) -> Self:
        logger.info(f"trying to stop service {self}")
        self._state = ServiceState.INTERRUPTED
        stop_all_children(self)

        def _interrupt():
            logger.info(f"interrupting service {self}")
            self._interrupted.set_result(None)

        self._main_task.get_loop().call_soon_threadsafe(_interrupt)
        return self

    async def __run_wrapper(self):
        with self.context():
            try:
                print(multiprocessing.current_process())
                await self.run()
            except Exception as ex:
                if not self._started.done():
                    self._state = ServiceState.START_FAILED
                else:
                    self._state = ServiceState.STOPPED

                for future in (self._started, self._interrupted, self._stopped):
                    if not future.done():
                        self._started.set_exception(ex)
            finally:
                if not self._stopped.done():
                    self._stopped.set_result(None)
                await self._stop_queues_processing()

    async def _stop_queues_processing(self):
        await asyncio.gather(self._in_queue.join(), self._out_queue.join())
        self._in_queue_processing_task.cancel()
        self._out_queue_processing_task.cancel()

    @abstractmethod
    async def run(self):
        ...

    @classmethod
    def wrap(cls: Type['AsyncioService'], run_function: Callable[['AsyncManagedEnv'], Coroutine]) -> 'AsyncioService':
        class _AnonAsyncioService(cls):
            async def run(self):
                await run_function(AsyncServiceManagedEnv(self))

        return _AnonAsyncioService()

    @classmethod
    def combine_async(cls, *services: 'AsyncioService') -> 'AsyncioService':
        class _AnonAsyncioService(AsyncioService):
            def __init__(self):
                super().__init__()
                for service in services:
                    self.add_child(service)

                self.add_message_listener(lambda message: proxy_message_to_all_children(message, self))

            async def run(self):
                for service in services:
                    await service.started()
                self._mark_started()
                await asyncio.sleep(3)

                await self.interrupted()
                for service in services:
                    await service.stopped()

        return _AnonAsyncioService()

    @staticmethod
    async def wait_for(future: asyncio.Future, timeout: ServiceTimeout = None):
        await asyncio.wait_for(future, timeout_seconds(timeout))


def queue_messages_processing_task(
    queue: asyncio.Queue,
    processors: list[Callable[[Any], ...]],
) -> asyncio.Task:
    async def handle_messages():
        while not asyncio.current_task().cancelled():
            message = await queue.get()
            for processor in processors:
                try:
                    if inspect.iscoroutinefunction(processor):
                        await processor(message)
                    else:
                        processor(message)
                except Exception as ex:
                    logger.exception("exception on message handling")
            queue.task_done()

    return asyncio.create_task(handle_messages())


class AsyncManagedEnv(Protocol):
    def interrupted(self) -> asyncio.Future:
        ...

    def started(self) -> asyncio.Future:
        ...

    def mark_started(self):
        ...

    def add_message_handler(self, handler: Callable):
        ...

    def send_message_out(self, message):
        ...

    def add_child(self, service: Service):
        ...


class AsyncServiceManagedEnv:
    def __init__(self, service: AsyncioService) -> None:
        self.__service = service

    def interrupted(self) -> asyncio.Future:
        return self.__service.interrupted()

    def started(self) -> asyncio.Future:
        return self.__service.started()

    def mark_started(self):
        self.__service._mark_started()

    def add_message_handler(self, handler: Callable):
        self.__service._add_message_handler(handler)

    def send_message_out(self, message):
        self.__service._send_message_out(message)

    def add_child(self, service: Service):
        self.__service.add_child(service)
