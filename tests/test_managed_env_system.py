import asyncio
import time
from typing import Any

from frontik.boksh.service.aio import _start_queue_processing, AsyncManagedEnv, AsyncioService
from frontik.boksh.service.common import get_state_symbol, ServiceState
from frontik.boksh.service.sync import ProcessService, ManagedEnvSync


def test_huemoe():
    def main(menv: ManagedEnvSync):
        for i in range(10):
            menv.send_message_out(i)

    main_service = ProcessService.wrap(main).add_message_listener(lambda m: print(m)).start()

    time.sleep(5)
    # print(main_service.stopped())
    main_service.wait_for(main_service.stopped())
    # while not queue.empty():


def test_asyncio_service_send_receive_msg():
    async def print_and_sleep(menv: AsyncManagedEnv):
        value = 1

        def _send_message_back(message: str | Any):
            nonlocal value
            value += 1
            print(f"got message: {message}")
            menv.send_message_out("response " + message)
            if value == 10:
                menv.send_message_out(get_state_symbol(ServiceState.INTERRUPTED))

        menv.add_message_handler(_send_message_back)
        menv.mark_started()
        while not menv.interrupted():
            await asyncio.sleep(1)
            print('sleeping')
        print("exit")

    async def main():
        service = AsyncioService.wrap(print_and_sleep)

        service.start()
        service.send_message("message")
        await asyncio.sleep(1)
        print("after_sleep")
        service.stop()

    asyncio.run(main())


def test_huemoees():
    result = []

    async def print_and_sleep(m):
        result.append(m)
        await asyncio.sleep(1)

    async def main():
        queue = asyncio.Queue()
        for m in range(5):
            queue.put_nowait(m)
        task = _start_queue_processing(queue, [print_and_sleep])
        await asyncio.sleep(1)

        await queue.join()
        task.cancel()

    asyncio.run(main())

    assert len(result) == 5
