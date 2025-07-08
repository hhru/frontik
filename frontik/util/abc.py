from asyncio import iscoroutinefunction
from typing import Any


# This class will delegate all calls except for those which were overridden by descendants
# a Main use case is for Cython code. Not every class/method in cython can be overridden.
class Delegator:
    def __init__(self, delegator: Any) -> None:  # noqa: ANN401
        self.delegator = delegator

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        attr = getattr(self.delegator, name)
        if callable(attr):
            if iscoroutinefunction(attr):

                async def async_method_wrapper(*args: Any, **kwargs: dict[str, Any]) -> Any:  # noqa: ANN401
                    return await attr(*args, **kwargs)

                return async_method_wrapper
            else:

                def sync_method_wrapper(*args: Any, **kwargs: dict[str, Any]) -> Any:  # noqa: ANN401
                    return attr(*args, **kwargs)

                return sync_method_wrapper
        return attr
