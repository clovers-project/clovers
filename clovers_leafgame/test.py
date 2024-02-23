import asyncio
import time


async def func(task_list):
    for _ in range(100000):
        flag = await asyncio.gather(*task_list) if task_list else None


async def main():
    start = time.time()
    await None
    print(time.time() - start)


asyncio.run(main())
