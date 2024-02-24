import inspect
from collections.abc import Coroutine, Callable


def kwfilter(func: Callable[..., Coroutine]):
    kw = inspect.signature(func).parameters.keys()
    if kw:

        async def wrapper(*args, **kwargs):
            return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    else:

        async def wrapper(*args, **kwargs):
            return await func()

    return wrapper
