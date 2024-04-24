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
        try:
            return self.kwarg_dict[key]
        except KeyError:
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
        result = await handle(event)
        if not result:
            return 0
        await self.send_method(result.send_method)(result.data, **extra)
        return 1

    async def response_safe(self, *args):
        try:
            return await self.response(*args)
        except:
            traceback.print_exc()
            return 0


class Adapter:
    def __init__(self) -> None:
        self.global_method: AdapterMethod = AdapterMethod()
        self.plugins: list[Plugin] = []
        self.method_dict: dict[str, AdapterMethod] = {}
        self.plugins_dict: dict[str, list[Plugin]] = {}
        self.wait_for: list[Awaitable] = []

    async def response(self, adapter_key: str, command: str, **extra) -> int:
        task_list = []
        adapter_method = self.method_dict[adapter_key]
        plugins = self.plugins_dict[adapter_key]
        for plugin in plugins:
            if data := plugin(command):
                task_list.extend(adapter_method.response_safe(plugin.handles[key], event, extra) for key, event in data.items())
            if plugin.temp_check():
                event = Event(command, [])
                task_list.extend(adapter_method.response_safe(handle, event, extra) for _, handle in plugin.temp_handles.values())
        return sum(await asyncio.gather(*task_list)) if task_list else 0

    async def startup(self):
        task_list = [task for plugin in self.plugins for task in plugin.startup_tasklist]
        self.wait_for.append(asyncio.gather(*task_list))
        self.wait_for.extend(task for plugin in self.plugins for task in plugin.shutdown_tasklist)
        # 混合全局方法
        # 过滤没有指令响应任务的插件
        # 检查任务需求的参数是否存在于响应器获取参数方法。
        method_extra_args: dict[str, set[str]] = {}
        for key, method in self.method_dict.items():
            method.remix(self.global_method)
            self.plugins_dict[key] = []
            method_extra_args[key] = set(method.kwarg_dict.keys())
        for plugin in self.plugins:
            if not plugin.handles:
                continue
            extra_args: set[str] = set()
            extra_args = extra_args.union(*[set(handle.extra_args) | set(handle.get_extra_args) for handle in plugin.handles.values()])
            for key, v in method_extra_args.items():
                if method_miss := extra_args - v:
                    print(f"由于适配器方法：{key} 未定义kwarg方法{method_miss}，{key}将不响应{plugin.name}")
                else:
                    self.plugins_dict[key].append(plugin)
        self.plugins.clear()

    async def shutdown(self):
        await asyncio.gather(*self.wait_for)

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()
