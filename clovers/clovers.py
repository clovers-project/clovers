import asyncio
from collections.abc import Awaitable
from .plugin import Plugin, Event
from .adapter import Adapter
from .logger import logger
from .tools import load_module


class Leaf:
    adapter: Adapter
    plugins: list[Plugin]
    wait_for: list[Awaitable]
    running: bool

    def __init__(self, adapter: Adapter) -> None:
        self.adapter = Adapter()
        self.adapter.remix(adapter)
        self.plugins = []
        self.wait_for = []
        self.running = False

    async def startup(self):
        self.plugins.sort(key=lambda plugin: plugin.priority)
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.startup_tasklist)
        # 过滤没有指令响应任务的插件
        # 检查任务需求的参数是否存在于响应器获取参数方法。
        adapter_properties = set(self.adapter.properties_lib.keys())
        plugins = []
        for plugin in self.plugins:
            if not plugin.ready():
                continue
            plugin_properties: set[str] = set().union(*[set(handle.properties) for handle in plugin.handles])
            if method_miss := plugin_properties - adapter_properties:
                logger.warning(
                    f'插件 "{plugin.name}" 声明了适配器 "{self.adapter.name}" 未定义的 property 方法',
                    extra={"method_miss": method_miss},
                )
                logger.debug(f'"{self.adapter.name}"未定义的 property 方法:{method_miss}')
                continue
            plugins.append(plugin)
        self.plugins.clear()
        self.plugins.extend(plugins)
        self.running = True

    async def shutdown(self):
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.shutdown_tasklist)
        await asyncio.gather(*self.wait_for)
        self.running = False

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    async def response(self, command: str, /, **extra) -> int:
        count = 0
        for plugin in self.plugins:
            if plugin.temp_check():
                event = Event(command, [])
                flags = await asyncio.gather(*[self.adapter.response(handle, event, extra) for _, handle in plugin.temp_handles.values()])
                flags = [flag for flag in flags if not flag is None]
                if flags:
                    count += len(flags)
                    if any(flags):
                        if plugin.block:
                            break
                        continue
            if data := plugin(command):
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


class Clovers:
    def __init__(self) -> None:
        self.adapter: Adapter = Adapter()
        self.plugins: list[Plugin] = []
        self.adapters: dict[str, Adapter] = {}

    def leaf(self, key: str):
        leaf = Leaf(self.adapters[key])
        leaf.adapter.name = key
        leaf.adapter.remix(self.adapter)
        leaf.plugins.extend(self.plugins)
        return leaf

    def register_plugin(self, plugin: Plugin):
        if plugin.name in self.plugins:
            logger.warning(f"plugin {plugin.name} already loaded")
        else:
            self.plugins.append(plugin)

    def load_plugin(self, name: str):
        logger.info(f"【loading plugin】 {name} ...")
        try:
            plugin = load_module(name, "__plugin__")
        except Exception as e:
            logger.exception(f"plugin {name} load failed", exc_info=e)
            return
        if isinstance(plugin, Plugin):
            plugin.name = plugin.name or name
            self.register_plugin(plugin)

    def load_plugins(self, namelist: list[str]):
        for name in namelist:
            self.load_plugin(name)

    def register_adapter(self, adapter: Adapter):
        if adapter.name in self.adapters:
            self.adapters[adapter.name].remix(adapter)
            logger.info(f"{adapter.name} remixed")
        else:
            self.adapters[adapter.name] = adapter

    def load_adapter(self, name: str):
        logger.info(f"【loading adapter】 {name} ...")
        try:
            adapter = load_module(name, "__adapter__")
        except Exception as e:
            logger.exception(f"plugin {name} load failed", exc_info=e)
            return
        if isinstance(adapter, Adapter):
            adapter.name = adapter.name or name
            self.register_adapter(adapter)

    def load_adapters(self, namelist: list[str]):
        for name in namelist:
            self.load_adapter(name)
