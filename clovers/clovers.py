import asyncio
import abc
from importlib import import_module
from pathlib import Path
from .core import Plugin, Event, Adapter
from typing import Any
from .typing import RunningTask
from .logger import logger


def import_path(path: str | Path):
    path = Path(path) if isinstance(path, str) else path
    return ".".join(path.relative_to(Path()).parts)


def list_modules(path: str | Path) -> list[str]:
    path = Path(path) if isinstance(path, str) else path
    import_path = ".".join(path.relative_to(Path()).parts)
    namelist = []
    for x in path.iterdir():
        name = x.stem if x.is_file() and x.name.endswith(".py") else x.name
        if name.startswith("_"):
            continue
        namelist.append(f"{import_path}.{name}")
    return namelist


class Leaf(abc.ABC):

    adapter: Adapter
    plugins: list[Plugin]
    wait_for: list[RunningTask]
    running: bool

    def __init__(self, name: str) -> None:
        self.adapter = Adapter(name)
        self.plugins = []
        self.wait_for = []
        self.running = False

    def load_adapter(self, name: str | Path, is_path=False):
        if is_path or isinstance(name, Path):
            import_name = import_path(name)
        else:
            import_name = name
        logger.info(f"[loading adapter] {import_name} ...")
        try:
            adapter = getattr(import_module(import_name), "__adapter__", None)
            assert isinstance(adapter, Adapter)
        except Exception as e:
            logger.exception(f"adapter {import_name} load failed", exc_info=e)
            return
        self.adapter.remix(adapter)

    def load_plugin(self, name: str | Path, is_path=False):
        if is_path or isinstance(name, Path):
            import_name = import_path(name)
        else:
            import_name = name
        logger.info(f"[loading plugin][{self.adapter.name}] {import_name} ...")
        try:
            plugin = getattr(import_module(import_name), "__plugin__", None)
            assert isinstance(plugin, Plugin)
        except Exception as e:
            logger.exception(f"plugin {import_name} load failed", exc_info=e)
            return
        key = plugin.name or import_name
        if plugin in self.plugins:
            logger.warning(f"plugin {key} already loaded")
        else:
            plugin.name = key
            self.plugins.append(plugin)

    def plugins_ready(self):
        """
        过滤没有指令响应任务的插件
        检查任务需求的参数是否存在于响应器获取参数方法。
        """

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

    async def startup(self):
        self.plugins.sort(key=lambda plugin: plugin.priority)
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.startup_tasklist)
        self.plugins_ready()
        self.running = True

    async def shutdown(self):
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.shutdown_tasklist)
        await asyncio.gather(*self.wait_for)
        self.running = False

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

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

    async def run(self) -> None:
        """
        async with self:
            while self.running:
                asyncio.create_task(self.response(**kwargs))
        """
        raise NotImplementedError
