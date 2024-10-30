import asyncio
import typing

_server_tasks: typing.Set[asyncio.Task] = set()
