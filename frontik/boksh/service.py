import asyncio
import concurrent.futures
import contextlib
import contextvars
import inspect
import logging
import multiprocessing
import multiprocessing as mp
import queue
import signal
import threading

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import TypeVar, Protocol, Generic, Callable, ClassVar, Type, Self, AsyncGenerator, Coroutine

T = TypeVar("T")

ServiceTimeout = timedelta | float | None

logger = logging.Logger(__file__)


def timeout_seconds(timeout: ServiceTimeout) -> float:
    if isinstance(timeout, float):
        return timeout
    return timeout.total_seconds() if timeout is not None else None


IM = TypeVar("IM")
OM = TypeVar("OM")


class MessagingInterface(Generic[IM, OM]):
    on_message: Callable[[IM], ...] | None
    send_message: Callable[[OM], ...]


class Service(Generic[T, IM, OM], ABC):
    name: str | None

    _current_service: ClassVar[contextvars.ContextVar] = contextvars.ContextVar("current_service")

    _running: T | None = None
    _started: T | None = None
    _interrupted: T | None = None
    _stopped: T | None = None

    children: dict[str, "Service"] = {}

    message_listeners: list[Callable[[OM], ...]] = []
    message_handlers: list[Callable[[OM], ...]] = []

    def __init__(self, name: str | None = None):
        super().__init__()
        self.name = name

    @abstractmethod
    def _state_getter(self, field: T) -> bool:
        ...

    @abstractmethod
    def _state_setter(self) -> T:
        ...

    @abstractmethod
    def send_message_in(self, message: IM):
        ...

    @abstractmethod
    def _send_message_out(self, message: OM):
        ...

    @abstractmethod
    def _add_message_handler(self, service_in_message_handler: Callable[[IM], ...]):
        ...

    @abstractmethod
    def add_listener(self, service_out_message_listener: Callable[[OM], ...]):
        ...

    def set_start_state(self):
        if self._running is None:
            self._running = self._state_setter()
            self._started = self._state_setter()
            self._interrupted = self._state_setter()
            self._stopped = self._state_setter()

    @abstractmethod
    def start(self) -> Self:
        ...

    @abstractmethod
    def stop(self) -> Self:
        ...

    def is_running(self) -> bool:
        return not self.is_stopped() and self._state_getter(self._running)

    def is_started(self) -> bool:
        return all(child.is_started() for child in self.children.values()) and self._state_getter(self._started)

    def is_interrupted(self) -> bool:
        return self._state_getter(self._interrupted)

    def is_stopped(self) -> bool:
        return all(child.is_stopped() for child in self.children.values()) and self._state_getter(self._stopped)

    def running(self) -> T:
        return self._running

    def started(self) -> T:
        return self._started

    def interrupted(self) -> T:
        return self._interrupted

    def stopped(self) -> T:
        return self._stopped

    def add_child(self, name: str, service: "Service"):
        logger.info(f"try register {service.name} as child for {self.name}")
        assert name not in self.children
        self.children[name] = service

    @abstractmethod
    def mark_start_success(self):
        ...

    @classmethod
    def current(cls) -> Self:
        return cls._current_service.get()

    @contextlib.contextmanager
    def context(self):
        token_global = _current_service_global.set(self)
        token_local = self._current_service.set(self)
        try:
            yield
        finally:
            self.__class__._current_service.reset(token_local)
            _current_service_global.reset(token_global)


_current_service_global = contextvars.ContextVar("_current_service_global")


def get_current_service() -> Service:
    return _current_service_global.get()


class AsyncioService(Service[asyncio.Future, IM, OM]):
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

    def send_message_in(self, message: IM):
        if self.message_handlers:
            self._task.get_loop().call_soon_threadsafe(lambda: self.in_queue.put_nowait(message))

    def _send_message_out(self, message: OM):
        if self.message_listeners:
            self.out_queue.put_nowait(message)

    def _add_message_handler(self, service_in_message_handler: Callable[[IM], ...]):
        need_to_start_listener = not self.message_handlers
        self.message_handlers.append(service_in_message_handler)
        if need_to_start_listener:
            start_message_listener_task(self.is_interrupted, self.in_queue, self.message_handlers)

    def add_listener(self, service_out_message_listener: Callable[[OM], ...]):
        need_to_start_listener = not self.message_listeners
        self.message_listeners.append(service_out_message_listener)
        if need_to_start_listener:
            start_message_listener_task(self.is_interrupted, self.in_queue, self.message_listeners)

    def start(self):
        self.set_start_state()

        if self._running.done():
            return None
        self._running.set_result(None)

        for name, child in self.children.items():
            child.start()

        self._task = asyncio.create_task(self.__run_wrapper())
        return self

    def mark_start_success(self):
        if not self._started.done():
            self._started.set_result(None)

    def stop(self) -> Self:
        for service_name, child_service in self.children.items():
            child_service.stop()
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
    def wrap(cls: Type['AsyncioService'], run_function: Callable[['ManagedEnv'], Coroutine]) -> 'AsyncioService':
        class _AnonAsyncioService(cls):
            async def run(self):
                await run_function(ServiceManagedEnv(self))

        return _AnonAsyncioService()

    @classmethod
    def combine(cls, *services):
        async def run():
            _self = cls.current()
            for i, service in enumerate(services):
                _self.add_child(f"Child{i}", service)

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


class ThreadService(Service[concurrent.futures.Future, IM, OM]):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        self.handle_messages = False
        self._in_current_thread: bool = False
        self._thread: threading.Thread | None = None

        self.in_queue: queue.Queue = queue.Queue()
        self.out_queue: queue.Queue = queue.Queue()

        self._message_handlers_thread: threading.Thread | None = None
        self._message_listeners_thread: threading.Thread | None = None

    def _state_getter(self, event: concurrent.futures.Future) -> bool:
        return event is not None and event.done()

    def _state_setter(self) -> concurrent.futures.Future:
        return concurrent.futures.Future()

    def in_current_thread(self, run_in_current: bool = True, /):
        self._in_current_thread = run_in_current

    def send_message_in(self, message: IM):
        if self.message_handlers:
            self.in_queue.put(message)

    def _send_message_out(self, message: OM):
        if self.message_listeners:
            self.out_queue.put(message)

    def _add_message_handler(self, service_in_message_handler: Callable[[IM], ...]):
        self.message_handlers.append(service_in_message_handler)
        if self._message_handlers_thread is None:
            self._message_handlers_thread = message_processing_thread(
                self.is_interrupted, self.in_queue, self.message_handlers
            )
            if self.is_running():
                self._message_handlers_thread.start()

    def add_listener(self, service_out_message_listener: Callable[[OM], ...]):
        self.message_listeners.append(service_out_message_listener)
        if self._message_listeners_thread is None:
            self._message_listeners_thread = message_processing_thread(
                self.is_interrupted, self.out_queue, self.message_listeners
            )
            if self.is_running():
                self._message_handlers_thread.start()

    def mark_start_success(self):
        if not self._started.done():
            self._started.set_result(None)

    def start(self):
        self.set_start_state()
        if self._message_handlers_thread:
            self._message_handlers_thread.start()
        if self._message_listeners_thread:
            self._message_listeners_thread.start()

        if self._running.done():
            return None
        self._running.set_result(None)

        for name, child in self.children.items():
            child.start()
        self._thread = threading.Thread(target=self.__run_wrapper, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> Self:
        for service_name, child_service in self.children.items():
            child_service.stop()
        self._interrupted.set_result(None)
        return self

    def __run_wrapper(self):
        with self.context():
            try:
                self.run()
            except Exception as ex:
                for future in (self._started, self._interrupted, self._stopped):
                    if not future.done():
                        self._started.set_exception(ex)
            self._stopped.set_result(None)

    @abstractmethod
    def run(self):
        ...

    @classmethod
    def wrap(cls: Type['ThreadService'], run_function: Callable[['ManagedEnv'], ...]) -> Type['ThreadService']:
        class _AnonThreadingService(cls):
            def run(self):
                run_function(ServiceManagedEnv(self))

        return _AnonThreadingService

    @staticmethod
    def wait_for(future: concurrent.futures.Future, timeout: ServiceTimeout = None):
        future.result(timeout_seconds(timeout))


class ProcessService(Service[mp.Event, IM, OM]):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        self._in_current_process: bool = False
        self._process: multiprocessing.Process | None = None

        self.in_queue: mp.Queue = mp.Queue()
        self.out_queue: mp.Queue = mp.Queue()

        self._has_listeners = mp.Event()
        self._has_handlers = mp.Event()
        self._message_handlers_thread: threading.Thread | None = None
        self._message_listeners_thread: threading.Thread | None = None

    def _state_getter(self, event: mp.Event) -> bool:
        return event is not None and event.is_set()

    def _state_setter(self) -> mp.Event:
        return mp.Event()

    def in_current_process(self, run_in_current: bool = True, /) -> Self:
        self._in_current_process = run_in_current
        return self

    def send_message_in(self, message: IM):
        if self._has_handlers.is_set():
            self.in_queue.put(message)

    def _send_message_out(self, message: OM):
        if self._has_listeners.is_set():
            self.out_queue.put(message)

    def _add_message_handler(self, service_in_message_handler: Callable[[IM], ...]):
        need_to_start_listener = not self._has_handlers.is_set()
        self.message_handlers.append(service_in_message_handler)
        if need_to_start_listener and not self._message_handlers_thread:
            self._has_handlers.set()
            self._message_handlers_thread = message_processing_thread(
                self.is_interrupted, self.in_queue, self.message_handlers
            )
            if self.is_running():
                self._message_handlers_thread.start()

    def add_listener(self, service_out_message_listener: Callable[[OM], ...]):
        need_to_start_listener = not self._has_listeners.is_set()
        self.message_listeners.append(service_out_message_listener)
        if need_to_start_listener and not self._message_listeners_thread:
            self._has_listeners.set()
            self._message_listeners_thread = message_processing_thread(
                self.is_interrupted, self.out_queue, self.message_listeners
            )
            if self.is_running():
                self._message_listeners_thread.start()

    def start(self) -> Self:
        self.set_start_state()
        if self._message_listeners_thread is not None:
            self._message_listeners_thread.start()
        if not self._in_current_process:
            self._process = multiprocessing.Process(target=self._run_wrapper)
            self._process.start()
        else:
            self._process = multiprocessing.current_process()
            self._run_wrapper()
        return self

    def stop(self) -> Self:
        # run in parent
        if mp.current_process() != self._process:
            self._process.terminate()
            return self

        # run in child
        for child in self.children.values():
            child.stop()
        self._interrupted.set()
        return self

    def mark_start_success(self):
        self._started.set()

    def _run_wrapper(self):
        with self.context():
            if self._message_handlers_thread is not None:
                self._message_handlers_thread.start()

            def sigterm_handler(signum, frame):
                print("got EVENT")
                self.stop()

            signal.signal(signal.SIGTERM, sigterm_handler)
            signal.signal(signal.SIGINT, sigterm_handler)

            try:
                self.run()
            except Exception as ex:
                logger.error(ex)
            finally:
                self._stopped.set()

    @abstractmethod
    def run(self):
        ...

    @classmethod
    def wrap(cls: Type['ProcessService'], run_function: Callable[['ManagedEnv'], ...]) -> 'ProcessService':
        return _AnonProcessService(run_function)

    @staticmethod
    def wait_for(event: mp.Event, timeout: ServiceTimeout = None):
        event.wait(timeout_seconds(timeout))

    @classmethod
    def wrap_async(cls: Type['ProcessService'], service: AsyncioService) -> 'ProcessService':
        def async_wrapper():
            async def xxx():
                service.start()
                await service.wait_for(service.started())
                cls.current().mark_start_success()
                await service.wait_for(service.stopped())

            return asyncio.run(xxx())

        return cls.wrap(async_wrapper)

    @classmethod
    def combine(cls, *services):
        async def run():
            _self = cls.current()
            for i, service in enumerate(services):
                _self.add_child(f"Child{i}", service)

            for service in services:
                service.start()

            for service in services:
                await service.started()

            for service in services:
                await service.interrupted()

        return cls.wrap(run)


class _AnonProcessService(ProcessService):
    def __init__(self, run_function: Callable[['ManagedEnv'], ...]):
        self.run_function = run_function
        super().__init__(None)

    def run(self):
        self.run_function(ServiceManagedEnv(self))


class ManagedEnv(Protocol):
    def is_interrupted(self) -> bool:
        ...

    def is_started(self) -> bool:
        ...

    def mark_started(self):
        ...

    def add_message_handler(self, handler):
        ...

    def send_message_out(self, message):
        ...


class ServiceManagedEnv:
    def __init__(self, service: Service) -> None:
        self.__service = service

    def is_interrupted(self) -> bool:
        return self.__service.is_interrupted()

    def is_started(self) -> bool:
        return self.__service.is_started()

    def mark_started(self):
        return self.__service.mark_start_success()

    def add_message_handler(self, handler):
        return self.__service._add_message_handler(handler)

    def send_message_out(self, message):
        return self.__service._send_message_out(message)


def message_processing_thread(interrupted: Callable[[], bool], queue: queue.Queue, processors: list[Callable]):
    def handle_messages():
        while not interrupted():
            message = queue.get()
            for processor in processors:
                try:
                    processor(message)
                except Exception as ex:
                    logger.exception("exception on message processing")

    return threading.Thread(target=handle_messages, daemon=True)


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
