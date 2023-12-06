import asyncio
import inspect
import logging
from abc import abstractmethod
from typing import Callable, Self, Type, Coroutine, Protocol, Any

from frontik.boksh.service.common import (
    Service,
    start_all_children,
    stop_all_children,
    proxy_message_to_all_children,
)
from frontik.boksh.service.timeout import ServiceTimeout, timeout_seconds

logger = logging.Logger(__file__)


class AsyncService(Service[asyncio.Future]):
    def __init__(self, address: str | None = None):
        super().__init__(address)
        self._main_task: asyncio.Task | None = None

        # in-out messaging
        self._in_queue_processing_task: asyncio.Task | None = None
        self._out_queue_processing_task: asyncio.Task | None = None
        self._in_queue: asyncio.Queue = asyncio.Queue()
        self._out_queue: asyncio.Queue = asyncio.Queue()

    def send_message(self, message: Any):
        if not self._interrupted.done():
            self._main_task.get_loop().call_soon_threadsafe(lambda: self._in_queue.put_nowait(message))

    def send_message_out(self, message: Any):
        self._main_task.get_loop().call_soon_threadsafe(lambda: self._out_queue.put_nowait(message))

    def start(self):
        if self.is_running():
            return
        logger.info(f"starting service {self}")
        self._started = asyncio.Future()
        self._interrupted = asyncio.Future()
        self._stopped = asyncio.Future()
        start_all_children(self)
        self._main_task = asyncio.create_task(self.__run_wrapper())
        return self

    def mark_started(self):
        if not self._started.done():
            self._started.set_result(None)
            self._in_queue_processing_task = queue_messages_processing_task(
                self._in_queue,
                self.in_message_handlers,
            )
            self._out_queue_processing_task = queue_messages_processing_task(
                self._out_queue,
                self.out_message_listeners,
            )

    def stop(self) -> Self:
        logger.info(f"trying to stop service {self}")
        stop_all_children(self)

        def _interrupt():
            logger.info(f"interrupting service {self}")
            self._interrupted.set_result(None)

        self._main_task.get_loop().call_soon_threadsafe(_interrupt)
        return self

    def is_interrupted(self) -> bool:
        return self._interrupted.done()

    def is_stopped(self) -> bool:
        return all(child.is_stopped() for child in self.children) and self._stopped.done()

    async def __run_wrapper(self):
        with self.context():
            try:
                await self.run()
            except Exception as ex:
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
    def wrap(cls: Type['AsyncService'], run_function: Callable[['AsyncManagedEnv'], Coroutine]) -> 'AsyncService':
        class _AnonAsyncioService(cls):
            async def run(self):
                await run_function(AsyncServiceManagedEnv(self))

        return _AnonAsyncioService()

    @classmethod
    def combine_async(cls, *services: 'AsyncService') -> 'AsyncService':
        class _AnonAsyncService(AsyncService):
            def __init__(self):
                super().__init__()
                for service in services:
                    self.add_child(service)

                self.add_message_listener(lambda message: proxy_message_to_all_children(message, self))

            async def run(self):
                for service in services:
                    await service.started()
                self.mark_started()

                await self.interrupted()
                for service in services:
                    await service.stopped()

        return _AnonAsyncService()

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

    def mark_started(self):
        ...

    def add_message_handler(self, handler: Callable):
        ...

    def send_message_out(self, message):
        ...

    def add_child(self, service: Service):
        ...


class AsyncServiceManagedEnv:
    def __init__(self, service: AsyncService) -> None:
        self.__service = service

    def interrupted(self) -> asyncio.Future:
        return self.__service.interrupted()

    def mark_started(self):
        self.__service.mark_started()

    def add_message_handler(self, handler: Callable):
        self.__service.add_message_handler(handler)

    def send_message_out(self, message):
        self.__service.send_message_out(message)

    def add_child(self, service: Service):
        self.__service.add_child(service)
