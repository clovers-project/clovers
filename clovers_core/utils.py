import inspect
from collections.abc import Coroutine, Callable


def kwfilter(func: Callable[..., Coroutine]):
    kw = inspect.signature(func).parameters.keys()
    if not kw:
        return lambda *args, **kwargs: func()

    async def wrapper(*args, **kwargs):
        return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    return wrapper
