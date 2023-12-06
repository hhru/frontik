import contextlib
import contextvars
from abc import ABC, abstractmethod
from enum import auto, IntEnum
from typing import Generic, ClassVar, Callable, Any, Self, TypeVar

T = TypeVar("T")


class ServiceState(IntEnum):
    NOT_STARTED = auto()
    STARTING = auto()
    STARTED = auto()
    START_FAILED = auto()
    INTERRUPTED = auto()
    STOPPED = auto()


ServiceStateSymbols = {
    ServiceState.NOT_STARTED: object(),
    ServiceState.STARTING: object(),
    ServiceState.STARTED: object(),
    ServiceState.START_FAILED: object(),
    ServiceState.INTERRUPTED: object(),
    ServiceState.STOPPED: object(),
}


def get_state_symbol(state: ServiceState):
    return ServiceStateSymbols[state]


class Service(Generic[T], ABC):
    _current_service: ClassVar[contextvars.ContextVar] = contextvars.ContextVar("current_service")

    _started: T | None = None
    _interrupted: T | None = None
    _stopped: T | None = None

    def __init__(self, address: Any | None = None):
        self.address = address or id(self)
        self.children: list["Service"] = []
        self.out_message_listeners: list[Callable[[Any], ...]] = []
        self.in_message_handlers: list[Callable[[Any], ...]] = []

    # @abstractmethod
    # def get_state(self) -> ServiceState:
    #     ...

    @abstractmethod
    def send_message(self, message: Any):
        ...

    @abstractmethod
    def send_message_out(self, message: Any):
        ...

    def add_message_handler(self, message_handler: Callable[[Any], ...]) -> Self:
        self.in_message_handlers.append(message_handler)
        return self

    def add_message_listener(self, message_listener: Callable[[Any], ...]) -> Self:
        self.out_message_listeners.append(message_listener)
        return self

    @abstractmethod
    def start(self) -> Self:
        ...

    @abstractmethod
    def _mark_started(self):
        ...

    @abstractmethod
    def stop(self) -> Self:
        ...

    def is_running(self) -> bool:
        return self.get_state() not in (ServiceState.NOT_STARTED, ServiceState.STOPPED)

    def is_started(self) -> bool:
        current_running = self.get_state() in (ServiceState.STARTED, ServiceState.INTERRUPTED)
        return current_running and all(child.is_started() for child in self.children)

    def is_interrupted(self) -> bool:
        return self.get_state() == ServiceState.INTERRUPTED

    def is_stopped(self) -> bool:
        return all(child.is_stopped() for child in self.children) and self.get_state() == ServiceState.STOPPED

    def started(self) -> T:
        return self._started

    def interrupted(self) -> T:
        return self._interrupted

    def stopped(self) -> T:
        return self._stopped

    def add_child(self, service: "Service"):
        self.children.append(service)

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


def start_all_children(service: Service):
    for child in service.children:
        child.start()


def stop_all_children(service: Service):
    for child in service.children:
        child.stop()


def proxy_message_to_all_children(message: Any, service: Service):
    for child in service.children:
        child.send_message(message)
