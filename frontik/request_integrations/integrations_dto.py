from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from frontik.frontik_response import FrontikResponse


class IntegrationDto:
    def __init__(self, value: Any = None) -> None:
        self.value = value
        self.response: Optional[FrontikResponse] = None

    def set_response(self, response: FrontikResponse) -> None:
        self.response = response

    def get_value(self) -> Any:
        return self.value
