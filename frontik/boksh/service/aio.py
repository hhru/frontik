import asyncio
import inspect
import logging
from abc import abstractmethod
from typing import Callable, Self, Type, Coroutine, Protocol, Any

from frontik.boksh.service import Service
from frontik.boksh.service.timeout import ServiceTimeout, timeout_seconds

logger = logging.Logger(__file__)


class AsyncioService(Service[asyncio.Future]):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        self._task: asyncio.Task | None = None
        self.handle_messages = False

        self.in_queue: asyncio.Queue = asyncio.Queue()
        self.out_queue: asyncio.Queue = asyncio.Queue()

    def _state_getter(self, event: asyncio.Future) -> bool:
        return event is not None and event.done()

    def _state_setter(self):
        return asyncio.Future()

    def send_message_in(self, message: Any):
        if self.message_handlers:
            self._task.get_loop().call_soon_threadsafe(lambda: self.in_queue.put_nowait(message))

    def _send_message_out(self, message: Any):
        if self.message_listeners:
            self.out_queue.put_nowait(message)

    def _add_message_handler(self, service_in_message_handler: Callable[[Any], ...]):
        need_to_start_listener = not self.message_handlers
        self.message_handlers.append(service_in_message_handler)
        if need_to_start_listener:
            start_message_listener_task(self.is_interrupted, self.in_queue, self.message_handlers)

    def add_listener(self, service_out_message_listener: Callable[[Any], ...]):
        need_to_start_listener = not self.message_listeners
        self.message_listeners.append(service_out_message_listener)
        if need_to_start_listener:
            start_message_listener_task(self.is_interrupted, self.in_queue, self.message_listeners)

    def start(self):
        self.set_start_state()

        if self._running.done():
            return None
        self._running.set_result(None)

        for child in self.children:
            child.start()

        self._task = asyncio.create_task(self.__run_wrapper())
        return self

    def mark_start_success(self):
        if not self._started.done():
            self._started.set_result(None)

    def stop(self) -> Self:
        for child in self.children:
            child.stop()
        asyncio.get_running_loop().call_soon_threadsafe(
            lambda: {
                self._interrupted.set_result(None),
                self._task.cancel(),
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
            self._stopped.set_result(None)

    @abstractmethod
    async def run(self):
        ...

    @classmethod
    def wrap(cls: Type['AsyncioService'], run_function: Callable[['ManagedEnvAsync'], Coroutine]) -> 'AsyncioService':
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


def start_message_listener_task(interrupted: Callable[[], bool], queue: asyncio.Queue, processors: list[Callable]):
    async def handle_messages():
        while not interrupted():
            message = await queue.get()
            for processor in processors:
                try:
                    if inspect.iscoroutinefunction(processor):
                        await processor(message)
                    else:
                        processor(message)
                except Exception as ex:
                    logger.exception("exception on message handling")

    asyncio.create_task(handle_messages())


class ManagedEnvAsync(Protocol):
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
        self.__service.mark_start_success()

    def add_message_handler(self, handler: Callable):
        self.__service._add_message_handler(handler)

    def send_message_out(self, message):
        self.__service._send_message_out(message)

    def add_child(self, service: Service):
        self.__service.add_child(service)
