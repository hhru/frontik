import asyncio
import inspect
import logging
from abc import abstractmethod
from typing import Callable, Self, Type, Coroutine, Protocol, Any

from frontik.boksh.service.common import Service, start_all_children, ServiceState, stop_all_children
from frontik.boksh.service.timeout import ServiceTimeout, timeout_seconds

logger = logging.Logger(__file__)


class AsyncioService(Service[asyncio.Future]):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        self._state = ServiceState.NOT_STARTED
        self._main_task: asyncio.Task | None = None
        self._in_queue_processing_task: asyncio.Task | None = None
        self._out_queue_processing_task: asyncio.Task | None = None

        self.in_queue: asyncio.Queue = asyncio.Queue()
        self.out_queue: asyncio.Queue = asyncio.Queue()

        def _start_queues_processing(_: AsyncioService):
            self._in_queue_processing_task = _start_queue_processing(self.in_queue, self.in_message_handlers)
            self._out_queue_processing_task = _start_queue_processing(self.out_queue, self.out_message_listeners)

        self.on_start_callbacks: list[Callable[[AsyncioService], ...]] = [
            start_all_children,
            _start_queues_processing,
        ]

    def _state_getter(self, event: asyncio.Future) -> bool:
        return event is not None and event.done()

    def get_state(self) -> ServiceState:
        return self._state

    def add_on_start_callback(self, callback: Callable[['AsyncioService'], ...]) -> Self:
        self.on_start_callbacks.append(callback)
        return self

    def send_message(self, message: Any):
        self._main_task.get_loop().call_soon_threadsafe(lambda: self.in_queue.put_nowait(message))

    def _send_message_out(self, message: Any):
        self._main_task.get_loop().call_soon_threadsafe(lambda: self.out_queue.put_nowait(message))

    def _add_message_handler(self, service_in_message_handler: Callable[[Any], ...]):
        self.in_message_handlers.append(service_in_message_handler)

    def add_message_listener(self, service_out_message_listener: Callable[[Any], ...]):
        self.out_message_listeners.append(service_out_message_listener)

    def start(self):
        if self.get_state() != ServiceState.NOT_STARTED:
            return
        self._state = ServiceState.STARTING
        self._started = asyncio.Future()
        self._interrupted = asyncio.Future()
        self._stopped = asyncio.Future()

        for cb in self.on_start_callbacks:
            cb(self)

        self._main_task = asyncio.create_task(self.__run_wrapper())
        return self

    def _mark_started(self):
        if not self._started.done():
            self._started.set_result(None)
            self._state = ServiceState.STARTED

    def stop(self) -> Self:
        stop_all_children(self)
        asyncio.get_running_loop().call_soon_threadsafe(
            lambda: {
                self._interrupted.set_result(None),
                self._main_task.cancel(),
            }
        )

        return self

    async def __run_wrapper(self):
        with self.context():
            try:
                await self.run()
            except Exception as ex:
                for future in (self._started, self._interrupted, self._stopped):
                    if not future.done():
                        self._started.set_exception(ex)
            finally:
                await self.stop_queues_processing()
            self._stopped.set_result(None)

    async def stop_queues_processing(self):
        await asyncio.gather(self.in_queue.join(), self.out_queue.join())
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
    def combine(cls, *services):
        async def run():
            _self = cls.current()
            for i, service in enumerate(services):
                _self.add_child(service)

            for service in services:
                service.start()

            for service in services:
                await service.started()

            for service in services:
                await service.interrupted()

        return cls.wrap(run)

    @staticmethod
    async def wait_for(future: asyncio.Future, timeout: ServiceTimeout = None):
        await asyncio.wait_for(future, timeout_seconds(timeout))


def _start_queue_processing(queue: asyncio.Queue, processors: list[Callable[[Any], ...]]) -> asyncio.Task:
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
                finally:
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
