from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Any, Callable
from abc import ABC, abstractmethod
import inspect

from frontik.app_integrations import Integration

if TYPE_CHECKING:
    from asyncio import Future
    from frontik.app import FrontikApplication


class SettingsClientInterface(ABC):
    @abstractmethod
    def get_str(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    def get_int(self, key: str) -> Optional[int]:
        pass

    @abstractmethod
    def get_bool(self, key: str) -> Optional[bool]:
        pass

    @abstractmethod
    def add_listener(self, pattern: str, callback: Callable[[str, str], None], trigger_current: bool = False) -> None:
        pass


def verify_settings_client_interface(obj: Any) -> bool:
    """Verify that an object implements the SettingsClientInterface contract.
    
    This function checks that the object has all required methods with correct signatures,
    without requiring inheritance from SettingsClientInterface.
    """
    required_methods = {
        'get_str': (str, Optional[str]),
        'get_int': (str, Optional[int]),
        'get_bool': (str, Optional[bool]),
        'add_listener': (str, Callable[[str, str], None], bool, None)
    }

    for method_name, expected_signature in required_methods.items():
        if not hasattr(obj, method_name):
            return False
        
        method = getattr(obj, method_name)
        if not callable(method):
            return False

        # Get the actual signature
        sig = inspect.signature(method)
        params = list(sig.parameters.values())
        
        # Check number of parameters
        if len(params) != len(expected_signature) - 1:  # -1 because return type is last
            return False

        # Check parameter types
        for param, expected_type in zip(params, expected_signature[:-1]):
            if param.annotation != expected_type:
                return False

        # Check return type
        if sig.return_annotation != expected_signature[-1]:
            return False

    return True


class SettingsClientStub(SettingsClientInterface):
    def get_str(self, key: str) -> Optional[str]:
        return None

    def get_int(self, key: str) -> Optional[int]:
        return None

    def get_bool(self, key: str) -> Optional[bool]:
        return None

    def add_listener(self, pattern: str, callback: Callable[[str, str], None], trigger_current: bool = False) -> None:
        pass


class SettingsClient(Integration):
    def __init__(self):
        pass

    def initialize_app(self, app: FrontikApplication) -> Optional[Future]:
        if hasattr(app, 'settings_client'):
            if not verify_settings_client_interface(app.settings_client):
                raise TypeError(
                    f"Existing settings_client does not implement required interface. "
                    f"Got {type(app.settings_client)}"
                )
            return None
        
        app.settings_client = SettingsClientStub()
        return None
