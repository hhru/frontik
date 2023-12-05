import contextlib
import contextvars
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Callable, ClassVar, Self, Any

T = TypeVar("T")


class Service(Generic[T], ABC):
    name: str | None

    _current_service: ClassVar[contextvars.ContextVar] = contextvars.ContextVar("current_service")

    _running: T | None = None
    _started: T | None = None
    _interrupted: T | None = None
    _stopped: T | None = None

    children: list["Service"] = []

    message_listeners: list[Callable[[Any], ...]] = []
    message_handlers: list[Callable[[Any], ...]] = []

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
    def send_message_in(self, message: Any):
        ...

    @abstractmethod
    def _send_message_out(self, message: Any):
        ...

    @abstractmethod
    def _add_message_handler(self, service_in_message_handler: Callable[[Any], ...]):
        ...

    @abstractmethod
    def add_listener(self, service_out_message_listener: Callable[[Any], ...]):
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
        return all(child.is_started() for child in self.children) and self._state_getter(self._started)

    def is_interrupted(self) -> bool:
        return self._state_getter(self._interrupted)

    def is_stopped(self) -> bool:
        return all(child.is_stopped() for child in self.children) and self._state_getter(self._stopped)

    def running(self) -> T:
        return self._running

    def started(self) -> T:
        return self._started

    def interrupted(self) -> T:
        return self._interrupted

    def stopped(self) -> T:
        return self._stopped

    def add_child(self, service: "Service"):
        self.children.append(service)

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
