import inspect
import asyncio
from collections.abc import Coroutine, Callable

from .plugin import Plugin


class AdapterError(Exception):
    def __init__(self, message: str, data=None):
        super().__init__(message)
        self.data = data


class AdapterMethod:
    def __init__(self) -> None:
        self.kwarg_dict: dict[str, Callable[..., Coroutine]] = {}
        self.send_dict: dict[str, Callable[..., Coroutine]] = {}

    def kwarg(self, method_name: str) -> Callable:
        """添加一个获取参数方法"""

        def decorator(func: Callable[..., Coroutine]):
            self.kwarg_dict[method_name] = self.kwfilter(func)

        return decorator

    def send(self, method_name: str) -> Callable:
        """添加一个发送消息方法"""

        def decorator(func: Callable[..., Coroutine]):
            self.send_dict[method_name] = self.kwfilter(func)

        return decorator

    @staticmethod
    def kwfilter(func: Callable[..., Coroutine]):
        kw = inspect.signature(func).parameters.keys()

        async def wrapper(*args, **kwargs):
            return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

        return wrapper


class Adapter:
    def __init__(self) -> None:
        self.methods: dict[str, AdapterMethod] = {}
        self.main_method: AdapterMethod = AdapterMethod()
        self.plugins: list[Plugin] = []

    async def response(self, adapter: str, command: str, **extra) -> int:
        method = self.methods[adapter]
        task_list = []
        for plugin in self.plugins:
            resp = plugin(command)
            for handle_id, event in resp.items():
                handle = plugin.handles[handle_id]
                handle.commands

                async def task():
                    kwargs_task = []
                    for key in handle.extra_args:
                        kwarg = method.kwarg.get(key) or self.main_method.kwarg.get(key)
                        if not kwarg:
                            raise AdapterError(f"未定义kwarg[{key}]方法", handle)
                        kwargs_task.append(kwarg(**extra))
                    kwargs = await asyncio.gather(*kwargs_task)
                    event.kwargs = {k: v for k, v in zip(handle.extra_args, kwargs)}
                    result = await handle(event)
                    if not result:
                        return 0
                    k = result.send_method
                    send = method.send.get(k) or self.main_method.send.get(k)
                    if not send:
                        raise AdapterError(f"使用了未定义的 send 方法:{k}")
                    await send(result.data)
                    return 1

                task_list.append(task)
        if task_list:
            flag = await asyncio.gather(*task_list)
            return sum(flag)

    async def task(self):
        await asyncio.gather(*(task for p in self.plugins for task in p.task_list))
