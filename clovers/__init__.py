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

    async def response(self, adapter_key: str, command: str, **extra) -> int:
        task_list = []
        adapter = self.adapter_dict[adapter_key]
        plugins = self.plugins_dict[adapter_key]
        for plugin in plugins:
            if data := plugin(command):
                task_list.extend(adapter.response_safe(plugin.handles[key], event, extra) for key, event in data.items())
            if plugin.temp_check():
                event = Event(command, [])
                task_list.extend(adapter.response_safe(handle, event, extra) for _, handle in plugin.temp_handles.values())
        return sum(await asyncio.gather(*task_list)) if task_list else 0

    def load_plugin(self, name: str):
        if self.wait_for:
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
        self.wait_for.extend(asyncio.create_task(task) for plugin in self.plugins for task in plugin.startup_tasklist)
        self.wait_for.extend(task for plugin in self.plugins for task in plugin.shutdown_tasklist)
        # 混合全局方法
        # 过滤没有指令响应任务的插件
        # 检查任务需求的参数是否存在于响应器获取参数方法。
        extra_args_dict: dict[str, set[str]] = {}
        for adapter_key, adapter in self.adapter_dict.items():
            adapter.remix(self.global_adapter)
            extra_args_dict[adapter_key] = set(adapter.kwarg_dict.keys())
            self.plugins_dict[adapter_key] = []

        for plugin in self.plugins:
            if not plugin.handles:
                continue
            extra_args: set[str] = set()
            extra_args = extra_args.union(*[set(handle.extra_args) | set(handle.get_extra_args) for handle in plugin.handles.values()])
            for adapter_key, existing in extra_args_dict.items():
                if method_miss := extra_args - existing:
                    logger.warning(
                        f'插件 "{plugin.name}" 声明了适配器 "{adapter_key}" 未定义的kwarg方法',
                        extra={"method_miss": method_miss},
                    )
                    logger.debug(f'"{adapter_key}"未定义的kwarg方法:{method_miss}')
                else:
                    self.plugins_dict[adapter_key].append(plugin)
        self.plugins.clear()

    async def shutdown(self):
        await asyncio.gather(*self.wait_for)

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()
