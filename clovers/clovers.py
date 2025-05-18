import asyncio
import abc
from importlib import import_module
from pathlib import Path
from .core import Plugin, Event, Adapter
from .utils import import_path
from typing import Any
from .typing import RunningTask
from .logger import logger


class CloversCore:
    """
    四叶草核心：此处管理插件的加载和准备，是各种实现的基础
    """

    name: str = "CloversObject"
    plugins: list[Plugin]

    def __init__(self):
        self.plugins = []

    def load_plugin(self, name: str | Path, is_path=False):
        if is_path or isinstance(name, Path):
            import_name = import_path(name)
        else:
            import_name = name
        logger.info(f"[loading plugin][{self.name}] {import_name} ...")
        try:
            plugin = getattr(import_module(import_name), "__plugin__", None)
            assert isinstance(plugin, Plugin)
        except Exception as e:
            logger.exception(f"plugin {import_name} load failed", exc_info=e)
            return
        key = plugin.name or import_name
        if plugin in self.plugins:
            logger.warning(f"plugin {key} already loaded")
            return
        plugin.name = key
        self.plugins.append(plugin)

    def plugins_ready(self):
        """
        实现插件的准备逻辑，一般为执行 plugin.ready() 时进行一些处理
        """
        self.plugins = [plugin for plugin in self.plugins if plugin.ready()]


class Client(abc.ABC, CloversCore):
    """clovers客户端基类"""

    wait_for: list[RunningTask]
    running: bool

    def __init__(self) -> None:
        super().__init__()
        self.wait_for = []
        self.running = False

    async def startup(self):
        if self.running:
            raise RuntimeError("Client is already running")
        self.plugins.sort(key=lambda plugin: plugin.priority)
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.startup_tasklist)
        self.plugins_ready()
        self.running = True

    async def shutdown(self):
        if not self.running:
            raise RuntimeError("Client is not running")
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.shutdown_tasklist)
        await asyncio.gather(*self.wait_for)
        self.wait_for.clear()
        self.running = False

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    @abc.abstractmethod
    async def run(self) -> None:
        """
        Run the client
        .. code-block:: python3
            '''
            async with self:
                while self.running:
                    pass
            '''
        """
        raise NotImplementedError


class Leaf(abc.ABC, CloversCore):
    """clovers 适配器响应处理基类"""

    adapter: Adapter

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.adapter = Adapter(name)

    def load_adapter(self, name: str | Path, is_path=False):
        if is_path or isinstance(name, Path):
            import_name = import_path(name)
        else:
            import_name = name
        logger.info(f"[loading adapter][{self.name}] {import_name} ...")
        try:
            adapter = getattr(import_module(import_name), "__adapter__", None)
            assert isinstance(adapter, Adapter)
        except Exception as e:
            logger.exception(f"adapter {import_name} load failed", exc_info=e)
            return
        self.adapter.remix(adapter)

    def plugins_ready(self):
        adapter_properties = set(self.adapter.properties_lib.keys())
        plugins = []
        for plugin in self.plugins:
            if not plugin.ready():
                continue
            plugin_properties = {p for handle in plugin.handles for p in handle.properties}
            if method_miss := plugin_properties - adapter_properties:
                logger.warning(f'Plugin "{plugin.name}" requires method not defined by Adapter "{self.adapter.name}"')
                logger.debug(f'Undefined property methods in "{self.adapter.name}": {method_miss}', extra={"method_miss": method_miss})
                continue
            plugins.append(plugin)
        self.plugins.clear()
        self.plugins.extend(plugins)

    async def response_message(self, message: str, /, **extra):
        count = 0
        temp_event = None
        for plugin in self.plugins:
            if plugin.temp_check():
                temp_event = temp_event or Event(message, [])
                flags = [
                    flag
                    for flag in await asyncio.gather(
                        *(
                            self.adapter.response(handle, temp_event, extra)  # 同时执行临时任务
                            for _, handle in plugin.temp_handles_dict.values()
                        )
                    )
                    if not flag is None
                ]
                if flags:
                    count += len(flags)
                    if any(flags):
                        if plugin.block:
                            break
                        else:
                            continue
            if data := plugin.command_match(message):
                inner_count = 0
                for handle, event in data:
                    flag = await self.adapter.response(handle, event, extra)
                    if flag is None:
                        continue
                    inner_count += 1
                    if flag:
                        break
                count += inner_count
                if inner_count > 0 and plugin.block:
                    break
        return count

    async def response_key(self, key, /, **extra) -> int:
        count = 0
        temp_event = None
        for plugin in self.plugins:
            if plugin.temp_check():
                temp_event = temp_event or Event("", [])
                flags = [
                    flag
                    for flag in await asyncio.gather(
                        *(
                            self.adapter.response(handle, temp_event, extra)  # 同时执行临时任务
                            for _, handle in plugin.temp_handles_dict.values()
                        )
                    )
                    if not flag is None
                ]
                if flags:
                    count += len(flags)
                    if any(flags):
                        if plugin.block:
                            break
                        else:
                            continue
            if data := plugin.key_match(key):
                inner_count = 0
                for handle, event in data:
                    flag = await self.adapter.response(handle, event, extra)
                    if flag is None:
                        continue
                    inner_count += 1
                    if flag:
                        break
                count += inner_count
                if inner_count > 0 and plugin.block:
                    break
        return count

    @abc.abstractmethod
    def extract_message(self, **extra) -> str | None:
        raise NotImplementedError

    def extract_key(self, **extra) -> Any | None:
        return None

    async def response(self, **extra) -> int:
        if (message := self.extract_message(**extra)) is not None:
            return await self.response_message(message, **extra)
        elif (key := self.extract_key(**extra)) is not None:
            return await self.response_key(key, **extra)
        return 0


class LeafClient(Leaf, Client):
    """
    单适配器响应客户端
    """
