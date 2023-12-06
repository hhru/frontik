import asyncio
import concurrent.futures
import logging
import multiprocessing
import queue
import signal
import threading
from abc import abstractmethod
from multiprocessing.synchronize import Event
from typing import Callable, Self, Type, Any, Protocol

import multiprocess as mp

from frontik.boksh.service.aio import AsyncService
from frontik.boksh.service.common import Service, ServiceState, start_all_children, stop_all_children
from frontik.boksh.service.timeout import timeout_seconds, ServiceTimeout

logger = logging.Logger(__file__)

SyncEvent = threading.Event | multiprocessing.synchronize.Event
SyncQueue = queue.Queue | multiprocessing.JoinableQueue


class SyncService(Service[concurrent.futures.Future]):
    def __init__(
        self,
        event_factory: Callable[[], SyncEvent],
        queue_factory: Callable[[], SyncQueue],
        address: str | None = None,
    ):
        super().__init__(address)
        self._in_current_env: bool = False

        self._interrupted_event = event_factory()
        self._stopped_event = event_factory()
        self._started_event = event_factory()

        # in-out messaging
        self._in_queue: queue.Queue | multiprocessing.JoinableQueue = queue_factory()
        self._out_queue: queue.Queue | multiprocessing.JoinableQueue = queue_factory()
        self._message_handlers_thread: threading.Thread | multiprocessing.Process | None = None
        self._message_listeners_thread: threading.Thread | multiprocessing.Process | None = None
        self._queues_joined: threading.Event | multiprocessing.Event | None = None

    def __create_income_messages_processing_thread(self):
        return queue_messages_processing_thread(
            self._queues_joined.is_set,
            self._in_queue,
            self.in_message_handlers,
        )

    def __create_outcome_messages_processing_thread(self):
        return queue_messages_processing_thread(
            self._queues_joined.is_set,
            self._out_queue,
            self.out_message_listeners,
        )

    def send_message(self, message: Any):
        if not self._interrupted_event.is_set():
            self._in_queue.put(message)

    def send_message_out(self, message: Any):
        self._out_queue.put(message)

    def _await_messaging_processing(self):
        self._in_queue.join()
        self._out_queue.join()
        self._queues_joined.set()

    @staticmethod
    def wait_for(future: concurrent.futures.Future, timeout: ServiceTimeout = None, skip_error: bool = False):
        try:
            future.result(timeout_seconds(timeout))
        except TimeoutError as ex:
            logger.exception(f"exception when waiting {future}")
            if not skip_error:
                raise ex


class ThreadService(SyncService):
    def __init__(self, address: str | None = None):
        super().__init__(event_factory=threading.Event, queue_factory=queue.Queue, address=address)
        self._thread: threading.Thread | None = None

        # in-out messaging
        self._in_queue: queue.Queue = queue.Queue()
        self._out_queue: queue.Queue = queue.Queue()
        self._message_handlers_thread: threading.Thread | None = None
        self._message_listeners_thread: threading.Thread | None = None
        self._queues_joined: threading.Event | None = None

    def in_current_thread(self, run_in_current: bool = True, /) -> Self:
        self._in_current_env = run_in_current
        return self

    def _mark_started(self):
        if not self._started.done():
            self._started.set_result(None)

            self._queues_joined = threading.Event()
            self._message_handlers_thread = self.__create_income_messages_processing_thread().start()
            self._message_listeners_thread = self.__create_outcome_messages_processing_thread().start()

    def start(self):
        if self._started is not None:
            return
        self._started = concurrent.futures.Future()
        self._interrupted = concurrent.futures.Future()
        self._stopped = concurrent.futures.Future()
        start_all_children(self)

        if self._in_current_env:
            self.__run_wrapper()
        else:
            self._thread = threading.Thread(target=self.__run_wrapper, daemon=True)
            self._thread.start()
        return self

    def stop(self) -> Self:
        stop_all_children(self)
        self._interrupted_event.set()
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
            finally:
                if not self._stopped.done():
                    self._stopped.set_result(None)
                self._await_messaging_processing()

    @abstractmethod
    def run(self):
        ...

    @classmethod
    def wrap(cls: Type['ThreadService'], run_function: Callable[['SyncManagedEnv'], ...]) -> 'ThreadService':
        class _AnonThreadingService(cls):
            def run(self):
                run_function(SyncServiceManagedEnv(self))

        return _AnonThreadingService()


class ProcessService(Service[mp.Event]):
    def __init__(self, address: Any | None = None):
        super().__init__(address)
        self._state = multiprocessing.Value('i', ServiceState.NOT_STARTED)
        self._in_current_process: bool = False
        self._process: mp.Process | None = None

        # in-out messaging
        self._in_queue: queue.Queue = queue.Queue()
        self._out_queue: queue.Queue = queue.Queue()
        self._message_handlers_thread: threading.Thread | None = None
        self._message_listeners_thread: threading.Thread | None = None
        self._queues_joined: threading.Event | None = None

    def in_current_process(self, run_in_current: bool = True, /) -> Self:
        self._in_current_process = run_in_current
        return self

    def get_state(self) -> ServiceState:
        return self._state.value

    def send_message(self, message: Any):
        self._in_queue.put(message)

    def add_message_listener(self, message_listener: Callable[[Any], ...]) -> Self:
        self.out_message_listeners.append(message_listener)
        return self

    def send_message_out(self, message: Any):
        self._out_queue.put(message)

    def add_message_handler(self, message_handler: Callable[[Any], ...]):
        self.in_message_handlers.append(message_handler)

    def start(self) -> Self:
        if self.get_state() != ServiceState.NOT_STARTED:
            return self
        self._state = ServiceState.STARTING

        self._started = multiprocessing.Event()
        self._interrupted = multiprocessing.Event()
        self._stopped = multiprocessing.Event()

        # if self._interrupted.is_set():
        #     self._started.set()
        #     self._stopped.set()
        #     return self

        if self._in_current_process:
            self._process = multiprocessing.current_process()
            self.__run_wrapper()
        else:
            self._process = mp.Process(target=self.__run_wrapper)
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

    def _mark_started(self):
        print(f"mark service {self} as started")
        self._started.set()

    def __run_wrapper(self):
        with self.context():
            # self._message_handlers_thread.start()

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
    def wrap(cls: Type['ProcessService'], run_function: Callable[['SyncManagedEnv'], ...]) -> 'ProcessService':
        class _AnonProcessService(ProcessService):
            def run(self):
                run_function(SyncServiceManagedEnv(self))

        return _AnonProcessService()

    @classmethod
    def wrap_async(cls: Type['ProcessService'], async_service: AsyncService) -> 'ProcessService':
        def async_wrapper(menv: SyncManagedEnv):
            async def main_coroutine():
                async_service.start()
                await async_service.started()
                menv.mark_started()
                await async_service.stopped()

            return asyncio.run(main_coroutine())

        process_service = cls.wrap(async_wrapper)
        # process_service.add_child(async_service)
        return process_service


def queue_messages_processing_thread(
    is_interrupted: Callable[[], bool],
    queue: queue.Queue,
    processors: list[Callable],
):
    def handle_messages():
        while not is_interrupted():
            message = queue.get()
            for processor in processors:
                try:
                    processor(message)
                except Exception as ex:
                    logger.exception("exception on message processing")
            queue.task_done()

    return threading.Thread(target=handle_messages, daemon=True)


class SyncManagedEnv(Protocol):
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


class SyncServiceManagedEnv:
    def __init__(self, service: SyncService) -> None:
        self.__service = service

    def is_interrupted(self) -> bool:
        return self.__service.is_interrupted()

    def is_started(self) -> bool:
        return self.__service.is_started()

    def mark_started(self):
        self.__service._mark_started()

    def add_message_handler(self, handler):
        self.__service.add_message_handler(handler)

    def send_message_out(self, message):
        self.__service.send_message_out(message)

    def add_child(self, service: Service):
        self.__service.add_child(service)
