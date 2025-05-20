import asyncio
import abc
from importlib import import_module
from pathlib import Path
from .core import Plugin, Event, Adapter
from .utils import import_path
from .typing import RunningTask
from .logger import logger


class CloversCore:
    """四叶草核心

    此处管理插件的加载和准备，是各种实现的基础

    Attributes:
        name (str): 项目名
        plugins (list[Plugin]): 项目管理的插件列表
    """

    name: str = "CloversObject"
    plugins: list[Plugin]

    def __init__(self):
        self.plugins = []

    def load_plugin(self, name: str | Path, is_path=False):
        """加载 clovers 插件

        Args:
            name (str | Path): 插件的包名或路径
            is_path (bool, optional): 是否为路径
        """
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
        """准备插件

        实现插件的准备逻辑，一般为执行 plugin.ready() 时进行一些处理
        """
        self.plugins = [plugin for plugin in self.plugins if plugin.ready()]


class Client(abc.ABC, CloversCore):
    """clovers 客户端基类

    Attributes:
        wait_for (list[RunningTask]): 运行中的任务列表
        running (bool): 客户端运行状态
    """

    wait_for: list[RunningTask]
    running: bool

    def __init__(self) -> None:
        super().__init__()
        self.wait_for = []
        self.running = False

    async def startup(self):
        """启动客户端

        如不在 async with 上下文中则要手动调用 startup() 方法，
        """
        if self.running:
            raise RuntimeError("Client is already running")
        self.plugins.sort(key=lambda plugin: plugin.priority)
        self.wait_for.extend(asyncio.create_task(task()) for plugin in self.plugins for task in plugin.startup_tasklist)
        self.plugins_ready()
        self.running = True

    async def shutdown(self):
        """关闭客户端

        如不在 async with 上下文中则要手动调用 shutdown() 方法，
        """
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
        运行 Clovers Client ，需要在子类中实现。

        .. code-block:: python3
            '''
            async with self:
                while self.running:
                    pass
            '''
        """
        raise NotImplementedError


class Leaf(abc.ABC, CloversCore):
    """clovers 响应处理器基类
    Attributes:
        adapter (Adapter): 对接响应的适配器
    """

    adapter: Adapter

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.adapter = Adapter(name)

    def load_adapter(self, name: str | Path, is_path=False):
        """加载 clovers 适配器

        会把目标适配器的方法注册到 self.adapter 中，如有适配器中已有同名方法则忽略

        Args:
            name (str | Path): 适配器的包名或路径
            is_path (bool, optional): 是否为路径
        """

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
        """响应消息

        Args:
            message (str): 消息内容
            **extra: 额外的参数

        Returns:
            int: 响应数量
        """
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

    @abc.abstractmethod
    def extract_message(self, **extra) -> str | None:
        """提取消息

        根据传入的事件参数提取消息

        Args:
            **extra: 额外的参数

        Returns:
            str | None: 消息
        """

        raise NotImplementedError

    async def response(self, **extra) -> int:
        """响应事件

        根据传入的事件参数响应事件。

        如果提取到了消息，则触发消息响应，如果提取到了事件，则触发事件响应。

        否则不会触发响应。

        Args:
            **extra: 额外的参数

        Returns:
            int: 响应数量
        """

        if (message := self.extract_message(**extra)) is not None:
            return await self.response_message(message, **extra)
        else:
            return 0


class LeafClient(Leaf, Client):
    """
    单适配器响应客户端
    """
