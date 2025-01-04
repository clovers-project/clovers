import asyncio
from collections.abc import Coroutine, Callable
from .plugin import Handle, Event
from .logger import logger


class AdapterError(Exception):
    def __init__(self, message: str, data=None):
        super().__init__(message)
        self.data = data


def kwfilter(func: Callable[..., Coroutine]):
    kw = set(func.__code__.co_varnames)
    if not kw:
        return lambda *args, **kwargs: func()

    async def wrapper(*args, **kwargs):
        return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    return wrapper


class Adapter:
    def __init__(self) -> None:
        self.name: str = ""
        self.kwarg_dict: dict[str, Callable[..., Coroutine]] = {}
        self.send_dict: dict[str, Callable[..., Coroutine]] = {}

    def kwarg(self, method_name: str) -> Callable:
        """添加一个获取参数方法"""

        def decorator(func: Callable[..., Coroutine]):
            self.kwarg_dict[method_name] = kwfilter(func)

        return decorator

    def send(self, method_name: str) -> Callable:
        """添加一个发送消息方法"""

        def decorator(func: Callable[..., Coroutine]):
            self.send_dict[method_name] = kwfilter(func)

        return decorator

    def remix(self, method: "Adapter"):
        """混合其他兼容方法"""
        for k, v in method.kwarg_dict.items():
            self.kwarg_dict.setdefault(k, v)
        for k, v in method.send_dict.items():
            self.send_dict.setdefault(k, v)

    def kwarg_method(self, key: str):
        try:
            return self.kwarg_dict[key]
        except KeyError:
            raise AdapterError(f"使用了未定义的 kwarg 方法：{key}")

    def send_method(self, key: str):
        if key in self.send_dict:
            return self.send_dict[key]
        else:
            raise AdapterError(f"使用了未定义的 send 方法：{key}")

    async def response(self, handle: Handle, event: Event, extra):
        try:
            if handle.extra_args:
                kwargs_task = []
                extra_args = []
                for key in handle.extra_args:
                    if key in event.kwargs:
                        continue
                    kwargs_task.append(self.kwarg_method(key)(**extra))
                    extra_args.append(key)
                event.kwargs.update({k: v for k, v in zip(extra_args, await asyncio.gather(*kwargs_task))})
            if handle.get_extra_args:
                for key in handle.get_extra_args:
                    if key in event.get_kwargs:
                        continue
                    if key in event.kwargs:

                        async def async_func():
                            return event.kwargs[key]

                        event.get_kwargs[key] = async_func
                        continue
                    event.get_kwargs[key] = lambda: self.kwarg_method(key)(**extra)
            result = await handle(event)
            if not result:
                return
            await self.send_method(result.send_method)(result.data, **extra)
            return handle.block
        except:
            logger.exception("response")
            return
