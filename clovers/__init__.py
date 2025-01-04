import asyncio
import importlib
from pathlib import Path
from collections.abc import Awaitable
from .core.plugin import Plugin, Event
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

    def load_plugin(self, name: str):
        if self.running:
            raise RuntimeError(f"cannot loading plugin after clovers startup")
        logger.info(f"【loading plugin】 {name} ...")
        plugin = self.load_module(name, "__plugin__")
        if plugin is None or not isinstance(plugin, Plugin):
            logger.info(f"{name} 已初始化")
        elif plugin not in self.plugins:
            plugin.name = plugin.name or name
            self.plugins.append(plugin)
            logger.info(f"{name} 加载成功")
        else:
            logger.info(f"{name} 已存在")

    def load_plugins(self, namelist: list[str]):
        for name in namelist:
            self.load_plugin(name)

    def load_adapter(self, name: str):
        if self.running:
            raise RuntimeError(f"cannot loading adapter after clovers startup")
        logger.info(f"【loading adapter】 {name} ...")
        adapter = self.load_module(name, "__adapter__")
        if adapter is None or not isinstance(adapter, Adapter):
            logger.info(f"{name} 已初始化")
        elif adapter.name in self.adapter_dict:
            self.adapter_dict[adapter.name].remix(adapter)
        else:
            self.adapter_dict[adapter.name] = adapter

    def load_adapters(self, namelist: list[str]):
        for name in namelist:
            self.load_adapter(name)

    @staticmethod
    def load_module(name: str, attr: str | None = None):
        try:
            module = importlib.import_module(name)
            if attr:
                return getattr(module, attr, None)
            return module
        except:
            logger.exception(name)

    @staticmethod
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
