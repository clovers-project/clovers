import asyncio
from collections.abc import Coroutine, Callable
from .typing import MethodLib
from .plugin import Handle, Event
from .logger import logger


def kwfilter(func: Callable[..., Coroutine]):

    co_argcount = func.__code__.co_argcount
    if co_argcount == 0:
        return lambda *args, **kwargs: func()
    kw = set(func.__code__.co_varnames[:co_argcount])

    async def wrapper(*args, **kwargs):
        return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    return wrapper


class Adapter:
    def __init__(self, name: str = "") -> None:
        self.name: str = name
        self.properties_lib: MethodLib = {}
        self.sends_lib: MethodLib = {}
        self.calls_lib: MethodLib = {}

    def property_method(self, method_name: str) -> Callable:
        """添加一个获取参数方法"""

        def decorator(func: Callable[..., Coroutine]):
            method = kwfilter(func)
            if method_name not in self.calls_lib:
                self.calls_lib[method_name] = method
            self.properties_lib[method_name] = method

        return decorator

    def send_method(self, method_name: str) -> Callable:
        """添加一个发送消息方法"""

        def decorator(func: Callable[..., Coroutine]):
            method = kwfilter(func)
            if method_name not in self.calls_lib:
                self.calls_lib[method_name] = method
            self.sends_lib[method_name] = method

        return decorator

    def call_method(self, method_name: str):
        """添加一个调用方法"""

        def decorator(func: Callable[..., Coroutine]):
            self.calls_lib[method_name] = kwfilter(func)

        return decorator

    def remix(self, adapter: "Adapter"):
        """混合其他兼容方法"""
        for k, v in adapter.properties_lib.items():
            self.properties_lib.setdefault(k, v)
        for k, v in adapter.sends_lib.items():
            self.sends_lib.setdefault(k, v)
        for k, v in adapter.calls_lib.items():
            self.calls_lib.setdefault(k, v)

    async def response(self, handle: Handle, event: Event, extra):
        try:
            if handle.properties:
                properties_task = []
                properties = []
                for key in handle.properties:
                    if key in event.properties:
                        continue
                    properties_task.append(self.properties_lib[key](**extra))
                    properties.append(key)
                event.properties.update({k: v for k, v in zip(properties, await asyncio.gather(*properties_task))})
            event.calls = self.calls_lib
            event.extra = extra
            result = await handle(event)
            if not result:
                return
            await self.sends_lib[result.send_method](result.data, **extra)
            return handle.block
        except:
            logger.exception("response")
