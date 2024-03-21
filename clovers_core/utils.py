from collections.abc import Coroutine, Callable


def kwfilter(func: Callable[..., Coroutine]):
    kw = set(func.__code__.co_varnames)
    if not kw:
        return lambda **kwargs: func()

    async def wrapper(**kwargs):
        return await func(**{k: v for k, v in kwargs.items() if k in kw})

    return wrapper
