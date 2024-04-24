import asyncio
import traceback
from collections.abc import Coroutine, Callable, Awaitable
from .plugin import Plugin, Handle, Event


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


class AdapterMethod:
    def __init__(self) -> None:
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

    def remix(self, method: "AdapterMethod"):
        """混合其他兼容方法"""
        for k, v in method.kwarg_dict.items():
            self.kwarg_dict.setdefault(k, v)
        for k, v in method.send_dict.items():
            self.send_dict.setdefault(k, v)

    def kwarg_method(self, key: str):
        if key in self.kwarg_dict:
            return self.kwarg_dict[key]
        else:
            raise AdapterError(f"使用了未定义的 kwarg 方法：{key}")

    def send_method(self, key: str):
        if key in self.send_dict:
            return self.send_dict[key]
        else:
            raise AdapterError(f"使用了未定义的 send 方法：{key}")

    async def response(self, handle: Handle, event: Event, extra: dict):
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


class Adapter:
    def __init__(self) -> None:
        self.methods: dict[str, AdapterMethod] = {}
        self.global_method: AdapterMethod = AdapterMethod()
        self.plugins: list[Plugin] = []
        self.wait_for: list[Awaitable] = []

    async def response_task(self, adapter_key: str, handle: Handle, event: Event, extra: dict):
        adapter_method = self.methods[adapter_key]
        if handle.extra_args:
            kwargs_task = []
            extra_args = []
            for key in handle.extra_args:
                if key in event.kwargs:
                    continue
                kwarg = adapter_method.kwarg_dict.get(key) or self.global_method.kwarg_dict.get(key)
                if not kwarg:
                    raise AdapterError(f"{adapter_key} 未定义kwarg[{key}]方法")
                kwargs_task.append(kwarg(**extra))
                extra_args.append(key)

            event.kwargs = {k: v for k, v in zip(extra_args, await asyncio.gather(*kwargs_task))}

        for key in handle.get_extra_args:
            if key in event.get_kwargs:
                continue
            if key in event.kwargs:

                async def async_func():
                    return event.kwargs[key]

                event.get_kwargs[key] = async_func
                continue
            kwarg = method.kwarg_dict.get(key) or self.method.kwarg_dict.get(key)
            if not kwarg:
                raise AdapterError(f"未定义kwarg[{key}]方法")
            event.get_kwargs[key] = lambda: kwarg(**extra)

        result = await handle(event)
        if not result:
            return 0
        send_method = result.send_method
        send = method.send_dict.get(send_method) or self.method.send_dict.get(send_method)
        if not send:
            raise AdapterError(f"使用了未定义的 send 方法:{send_method}")
        await send(result.data, **extra)
        return 1

    async def response_task_safe(self, *args):
        try:
            return await self.response_task(*args)
        except:
            traceback.print_exc()
            return 0

    async def response(self, adapter_key: str, command: str, **extra) -> int:
        task_list = []
        for plugin in self.plugins:
            if data := plugin(command):
                task_list += [self.response_task_safe(adapter_key, plugin.handles[key], event, extra) for key, event in data.items()]
            if plugin.temp_check():
                event = Event(command, [])
                task_list.extend(self.response_task_safe(adapter_key, handle, event, extra) for _, handle in plugin.temp_handles.values())
        return sum(await asyncio.gather(*task_list)) if task_list else 0

    async def startup(self):
        task_list = [task for plugin in self.plugins for task in plugin.startup_tasklist]
        self.wait_for.append(asyncio.gather(*task_list))
        self.wait_for.extend(task for plugin in self.plugins for task in plugin.shutdown_tasklist)
        self.plugins = [plugin for plugin in self.plugins if plugin.handles]
        for method in self.methods.values():
            method.remix(self.global_method)

    async def shutdown(self):
        await asyncio.gather(*self.wait_for)

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()
