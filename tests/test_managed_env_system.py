import asyncio
import multiprocessing
import time
from typing import Any

from frontik.boksh.service.aio import queue_messages_processing_task, AsyncManagedEnv, AsyncioService
from frontik.boksh.service.common import get_state_symbol, ServiceState
from frontik.boksh.service.sync import ProcessService, ManagedEnvSync, ThreadService


def test_huemoe():
    def main(menv: ManagedEnvSync):
        for i in range(10):
            menv.send_message_out(i)

    main_service = ProcessService.wrap(main).add_message_listener(lambda m: print(m)).start()

    time.sleep(5)
    # print(main_service.stopped())
    main_service.wait_for(main_service.stopped())
    # while not queue.empty():


def test_send_and_get_message_from_async_service():
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
            print(value)
        print("exit")

    async def main():
        service = AsyncioService.wrap(print_and_sleep)
        service.add_message_listener(lambda m: print(m))
        service.start()

        service.send_message("message1")
        service.send_message("message2")
        await asyncio.sleep(5)
        service.send_message("message3")
        print("after_sleep")
        service.stop()

    asyncio.run(main())


def test_combine_async_services():
    def get_listener(msg: str):
        async def listener(menv: AsyncManagedEnv):
            menv.mark_started()
            print(f"{asyncio.current_task()} {msg}")
            while not menv.interrupted().done():
                print(msg)
                await asyncio.sleep(1)

        return listener

    service = AsyncioService.combine_async(
        AsyncioService.wrap(get_listener("service1")),
        AsyncioService.wrap(get_listener("service2")),
    )

    async def main():
        service.start()
        await service.started()
        await asyncio.sleep(10)
        service.stop()
        await service.stopped()

    asyncio.run(main())


def test_run_async_service_inside_service():
    async def listener2(menv: AsyncManagedEnv):
        menv.mark_started()
        while not menv.interrupted().done():
            print("3333")
            await asyncio.sleep(1)

    def get_listener(msg: str):
        async def listener(menv: AsyncManagedEnv):
            subservice = AsyncioService.wrap(listener2).start()
            menv.add_child(subservice)
            await subservice.started()

            menv.mark_started()
            print(f"{asyncio.current_task()} {msg}")
            while not menv.interrupted().done():
                print(msg)
                await asyncio.sleep(1)

        return listener

    service = AsyncioService.combine_async(
        AsyncioService.wrap(get_listener("service1")),
        AsyncioService.wrap(get_listener("service2")),
    )

    async def main():
        service.start()
        await service.started()
        await asyncio.sleep(4)
        service.stop()
        await service.stopped()

    asyncio.run(main())


def test_thread_service_messaging():
    def main(menv: ManagedEnvSync):
        menv.mark_started()
        i = 1
        while not menv.is_interrupted():
            menv.send_message_out(i)
            i += 1
            time.sleep(1)

    main_service = ThreadService.wrap(main).add_message_listener(lambda m: print(m)).start()

    time.sleep(5)
    main_service.stop()
    main_service.wait_for(main_service.stopped())


def test_process_service_wrap_asyncio():
    def make_listener(msg):
        async def listener(menv: AsyncManagedEnv):
            menv.mark_started()
            while not menv.interrupted().done():
                print(msg)
                print(f"{asyncio.current_task()} {multiprocessing.current_process()}")
                await asyncio.sleep(1)
        return listener

    main_service1 = ProcessService.wrap_async(AsyncioService.wrap(make_listener("1234"))).start()
    main_service2 = ProcessService.wrap_async(AsyncioService.wrap(make_listener("456"))).start()

    time.sleep(3)
    main_service1.stop()
    main_service2.stop()
    # main_service.stop()
    # main_service.stopped()
