import asyncio
import concurrent.futures
import logging
import multiprocessing
import queue
import signal
import threading
from abc import abstractmethod
from typing import Callable, Self, Type, Any, Protocol

import multiprocess as mp

from frontik.boksh.service import Service
from frontik.boksh.service.aio import AsyncioService, ManagedEnvAsync
from frontik.boksh.service.timeout import timeout_seconds, ServiceTimeout

logger = logging.Logger(__file__)


class ThreadService(Service[concurrent.futures.Future]):
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

    def send_message_in(self, message: Any):
        if self.message_handlers:
            self.in_queue.put(message)

    def _send_message_out(self, message: Any):
        if self.message_listeners:
            self.out_queue.put(message)

    def _add_message_handler(self, service_in_message_handler: Callable[[Any], ...]):
        self.message_handlers.append(service_in_message_handler)
        if self._message_handlers_thread is None:
            self._message_handlers_thread = message_processing_thread(
                self.is_interrupted, self.in_queue, self.message_handlers
            )
            if self.is_running():
                self._message_handlers_thread.start()

    def add_listener(self, service_out_message_listener: Callable[[Any], ...]):
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
    def wrap(cls: Type['ThreadService'], run_function: Callable[['ManagedEnvSync'], ...]) -> Type['ThreadService']:
        class _AnonThreadingService(cls):
            def run(self):
                run_function(ServiceManagedEnv(self))

        return _AnonThreadingService

    @staticmethod
    def wait_for(future: concurrent.futures.Future, timeout: ServiceTimeout = None):
        future.result(timeout_seconds(timeout))


class ProcessService(Service[mp.Event]):
    def __init__(self, name: str | None = None):
        super().__init__(name)
        self._in_current_process: bool = False
        self._process: mp.Process | None = None

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

    def send_message_in(self, message: Any):
        if self._has_handlers.is_set():
            self.in_queue.put(message)

    def _send_message_out(self, message: Any):
        if self._has_listeners.is_set():
            self.out_queue.put(message)

    def _add_message_handler(self, service_in_message_handler: Callable[[Any], ...]):
        need_to_start_listener = not self._has_handlers.is_set()
        self.message_handlers.append(service_in_message_handler)
        if need_to_start_listener and not self._message_handlers_thread:
            self._has_handlers.set()
            self._message_handlers_thread = message_processing_thread(
                self.is_interrupted, self.in_queue, self.message_handlers
            )
            if self.is_running():
                self._message_handlers_thread.start()

    def add_listener(self, service_out_message_listener: Callable[[Any], ...]):
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
        if self._started:
            return
        self.set_start_state()

        if self._message_listeners_thread is not None:
            self._message_listeners_thread.start()

        if self._interrupted.is_set():
            self._started.set()
            self._stopped.set()
            return self

        if self._in_current_process:
            self._process = mp.current_process()
            self._run_wrapper()
        else:
            self._process = mp.Process(target=self._run_wrapper)
            self._process.start()
        return self

    def stop(self) -> Self:
        self._interrupted.set()
        # run in parent
        if mp.current_process() != self._process:
            self._process.terminate()
            return self

        # run in child
        for child in self.children:
            child.stop()
        return self

    def mark_start_success(self):
        self._started.set()

    def _run_wrapper(self):
        with self.context():
            if self._message_handlers_thread is not None:
                self._message_handlers_thread.start()

            def sigterm_handler(signum, frame):
                logger.info(f"got stop signal for {self}")
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
    def wrap(cls: Type['ProcessService'], run_function: Callable[['ManagedEnvSync'], ...]) -> 'ProcessService':
        class _AnonProcessService(ProcessService):
            def run(self):
                run_function(ServiceManagedEnv(self))

        return _AnonProcessService()

    @staticmethod
    def wait_for(event: multiprocessing.Event, timeout: ServiceTimeout = None):
        event.wait(timeout_seconds(timeout))

    @classmethod
    def wrap_async(cls: Type['ProcessService'], service: AsyncioService) -> 'ProcessService':
        def async_wrapper(menv: ManagedEnvSync):
            async def main_coroutine():
                service.start()
                await service.wait_for(service.started())
                cls.current().mark_start_success()
                await service.wait_for(service.stopped())

            return asyncio.run(main_coroutine())

        result = cls.wrap(async_wrapper)
        result.add_child(service)
        return result

    # @classmethod
    # def combine(cls, *services):
    #     def run():
    #         _self = cls.current()
    #         for service in services:
    #             _self.add_child(service)
    #
    #         for service in services:
    #             service.start()
    #
    #         for service in services:
    #             await service.started()
    #
    #         for service in services:
    #             await service.interrupted()
    #
    #     return cls.wrap(run)


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


class ManagedEnvSync(Protocol):
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

    def add_child(self, service: Service):
        ...


class ServiceManagedEnv:
    def __init__(self, service: ThreadService | ProcessService) -> None:
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

    def add_child(self, service: Service):
        self.__service.add_child(service)
