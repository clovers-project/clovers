import asyncio
import timeit

value = 2
match value:
    case 0:
        print("value is zero")
    case 1, 2, 3, 4:
        print(f"value is {value}")
    case _:
        print("value is something else")

for a in zip([1, 2], [3, 4]):
    print(a)


async def asyncfunc():
    print("Hello World")


def func():
    asyncio.create_task(asyncfunc())


async def main():
    func()
    while True:
        await asyncio.sleep(1)


asyncio.run(main())
