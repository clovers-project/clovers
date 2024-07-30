import asyncio
from collections.abc import Awaitable
from .core.plugin import Plugin, PluginLoader, Event
from .core.adapter import Adapter
from .core.logger import logger


class Clovers:
    def __init__(self) -> None:
        self.global_adapter: Adapter = Adapter()
        self.plugins: list[Plugin] = []
        self.adapter_dict: dict[str, Adapter] = {}
        self.plugins_dict: dict[str, list[Plugin]] = {}
        self.wait_for: list[Awaitable] = []
        self.running: bool = False

    async def response(self, adapter_key: str, command: str, /, **extra) -> int:
        adapter = self.adapter_dict[adapter_key]
        plugins = self.plugins_dict[adapter_key]
        count = 0
        for plugin in plugins:
            if plugin.temp_check():
                event = Event(command, [])
                flags = await asyncio.gather(*[adapter.response(handle, event, extra) for _, handle in plugin.temp_handles.values()])
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
                    flag = await adapter.response(handle, event, extra)
                    if flag is None:
                        continue
                    inner_count += 1
                    if flag:
                        break
                count += inner_count
                if inner_count > 0 and plugin.block:
                    break
        return count

    def load_plugin(self, name: str):
        if self.running:
            raise RuntimeError("cannot loading plugin after clovers startup")
        plugin = PluginLoader.load(name)
        if plugin is None:
            logger.error(f"未找到 {name}")
        elif plugin not in self.plugins:
            self.plugins.append(plugin)
            logger.info(f"{name} 加载成功")
        else:
            logger.info(f"{name} 已存在")

    async def startup(self):
        self.plugins.sort(key=lambda plugin: plugin.priority)
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.startup_tasklist)
        # 混合全局方法
        extra_args_dict: dict[str, set[str]] = {}
        for adapter_key, adapter in self.adapter_dict.items():
            adapter.remix(self.global_adapter)
            extra_args_dict[adapter_key] = set(adapter.kwarg_dict.keys())
            self.plugins_dict[adapter_key] = []
        # 过滤没有指令响应任务的插件
        # 检查任务需求的参数是否存在于响应器获取参数方法。
        for plugin in self.plugins:
            if not plugin.ready():
                continue
            extra_args: set[str] = set()
            extra_args = extra_args.union(*[set(handle.extra_args) | set(handle.get_extra_args) for handle in plugin.handles])
            for adapter_key, existing in extra_args_dict.items():
                if method_miss := extra_args - existing:
                    logger.warning(
                        f'插件 "{plugin.name}" 声明了适配器 "{adapter_key}" 未定义的kwarg方法',
                        extra={"method_miss": method_miss},
                    )
                    logger.debug(f'"{adapter_key}"未定义的kwarg方法:{method_miss}')
                else:
                    self.plugins_dict[adapter_key].append(plugin)
        self.running = True

    async def shutdown(self):
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.shutdown_tasklist)
        await asyncio.gather(*self.wait_for)

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()
