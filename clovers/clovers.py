import asyncio
from importlib import import_module
from pathlib import Path
from .core import Plugin, Event, Adapter
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


class Leaf:
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
