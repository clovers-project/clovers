import time
import asyncio
from abc import abstractmethod
from collections.abc import Iterable, Callable
from pathlib import Path
from importlib import import_module
from .utils import import_name, list_modules
from .protocol import protocol_format, check_compatible, is_coro
from ..base import Coro, Info, Adapter, AdapterMethod, AdapterMethodLib, BaseHandle, Event
from ..plugin import Handle, TempHandle, Plugin
from ..logger import logger


class CloversCore(Info):
    """四叶草核心

    此处管理插件的加载和准备，是各种实现的基础

    Attributes:
        name (str): 项目名
        plugins (list[Plugin]): 项目管理的插件列表
    """

    type HandleBatch = list[Handle]
    """同优先级的响应器组"""
    type TempHandleBatch = list[TempHandle]
    """同优先级的临时响应器组"""
    type HandleBatchQueue = list[HandleBatch]
    """按响应优先级排序的响应器组队列"""
    type HandleLayer = tuple[TempHandleBatch, HandleBatchQueue]
    """插件同一优先级下的响应器层"""

    def __init__(self):
        self.name: str = "CloversObject"
        """项目名"""
        self._plugins: list[Plugin] = []
        """插件优先级和插件列表"""
        self._layers_queue: list[CloversCore.HandleLayer] = []
        """已注册响应器队列"""
        self._ready: bool = False
        """插件是否就绪"""

    @property
    def info(self):
        return {"name": self.name, "plugins": self._plugins}

    @property
    def plugins(self):
        return (plugin for plugin in self._plugins)

    @plugins.setter
    def plugins(self, plugins: Iterable[Plugin]):
        if self._ready:
            raise RuntimeError("cannot set plugins after ready")
        self._plugins.clear()
        self._plugins.extend(plugins)

    def load_plugin(self, name: str | Path, is_path=False):
        """加载 clovers 插件

        Args:
            name (str | Path): 插件的包名或路径
            is_path (bool, optional): 是否为路径
        """
        package = import_name(name, is_path)
        try:
            plugin = getattr(import_module(package), "__plugin__", None)
            assert isinstance(plugin, Plugin)
        except Exception as e:
            logger.exception(f'[{self.name}][loading plugin] "{package}" load failed', exc_info=e)
            return
        key = plugin.name or package
        if plugin in self._plugins:
            return
        if plugin.require_plugins:
            for require_plugin in plugin.require_plugins:
                self.load_plugin(require_plugin)
        logger.info(f'[{self.name}][loading plugin] "{package}" loaded')
        plugin.name = key
        self._plugins.append(plugin)

    def load_plugins_from_list(self, plugin_list: list[str]):
        """从包名列表加载插件

        Args:
            plugin_list (list[str]): 插件的包名列表
        """
        for plugin in plugin_list:
            self.load_plugin(plugin)

    def load_plugins_from_dirs(self, plugin_dirs: list[str]):
        """从本地目录列表加载插件

        Args:
            plugin_dirs (list[str]): 插件的目录列表
        """
        for plugin_dir in plugin_dirs:
            plugin_dir = Path(plugin_dir)
            if not plugin_dir.exists():
                plugin_dir.mkdir(parents=True, exist_ok=True)
                continue
            for plugin in list_modules(plugin_dir):
                self.load_plugin(plugin)

    def handles_filter(self, handle: BaseHandle) -> bool:
        """任务过滤器

        Args:
            handle (Handle): 响应任务

        Returns:
            bool: 是否通过过滤
        """
        return True

    def plugin_check(self, plugin: Plugin) -> bool:
        """插件过滤器

        Args:
            plugin (Plugin): 插件

        Returns:
            bool: 是否通过过滤
        """

        return True

    def initialize_plugins(self):
        """初始化插件"""
        if self._ready:
            raise RuntimeError(f"{self.name} already ready")
        _temp_handles: dict[int, list[TempHandle]] = {}
        _handles: dict[int, list[Handle]] = {}
        self._plugins = [plugin for plugin in self._plugins if self.plugin_check(plugin)]
        for plugin in self._plugins:
            plugin.set_temp_handles(_temp_handles.setdefault(plugin.priority, []))
            _handles.setdefault(plugin.priority, []).extend(plugin.handles)
        for key in sorted(_handles.keys()):
            _sub_handles: dict[int, list[Handle]] = {}
            for handle in _handles[key]:
                if self.handles_filter(handle):
                    _sub_handles.setdefault(handle.priority, []).append(handle)
            sub_keys = sorted(_sub_handles.keys())
            self._layers_queue.append((_temp_handles[key], [_sub_handles[k] for k in sub_keys]))
        self._ready = True


class AdapterCore(Adapter):
    """适配器核心类

    Attributes:
        name (str, optional): 响应器名称. Defaults to "".
        sends_lib (AdapterMethodLib): 发送消息方法库
        calls_lib (AdapterMethodLib): 调用方法库
    """

    def __init__(self, name: str = "") -> None:
        self.name: str = name
        self.sends_lib: AdapterMethodLib = {}
        self.calls_lib: AdapterMethodLib = {}
        self.__protocol = {"send": {}, "call": {}}

    @property
    def info(self):
        return {
            "name": self.name,
            "sends_lib": list(self.sends_lib.keys()),
            "calls_lib": list(self.calls_lib.keys()),
        }

    def check_protocol(self, protocol: type | None):
        """检查适配器类型协议

        Args:
            data (type): 事件协议类型，包含字段和声明的类型
        """
        if protocol is None:
            return True
        check_protocol = protocol_format(protocol)
        for k in ["send", "call"]:
            if (self_fields := self.__protocol[k]) is None or (check_fields := check_protocol[k]) is None:
                continue
            keys = check_fields.keys() & self_fields.keys()
            for key in keys:
                if not check_compatible(self_fields[key], check_fields[key]):
                    logger.warning(
                        f"Adapter({self.name}) {k}[{key}] provides type '{self_fields[key]}', but protocol require '{check_fields[key]}'."
                    )
                    return False
        return True

    def send_decorator(self, method_name: str, func: AdapterMethod):
        if method_name in self.sends_lib:
            logger.warning(f"Method '{method_name}' already exists (from: {func.__module__}.{func.__qualname__})")
            return func
        name = func.__code__.co_varnames[0]
        if annot := func.__annotations__.get(name):
            self.__protocol["send"][method_name] = annot
        self.sends_lib[method_name] = func
        return func

    def call_decorator(self, method_name: str, func: AdapterMethod):
        if method_name in self.calls_lib:
            logger.warning(f"Method '{method_name}' already exists (from: {func.__module__}.{func.__qualname__})")
            return func
        co_posonlyargcount = func.__code__.co_posonlyargcount
        if co_posonlyargcount == 0:
            return self.property_method(method_name)(func)
        names = func.__code__.co_varnames[:co_posonlyargcount]
        fields = func.__annotations__
        if all(name in fields for name in names) and "return" in fields:
            if is_coro(func):
                self.__protocol["call"][method_name] = Callable[[fields[name] for name in names], Coro[fields["return"]]]
            else:
                self.__protocol["call"][method_name] = Callable[[fields[name] for name in names], fields["return"]]
        self.calls_lib[method_name] = func
        return func

    async def response(self, handle: BaseHandle, event: Event, extra: dict):
        """使用适配器响应任务

        Args:
            handle (BaseHandle): 触发的插件任务
            event (Event): 触发响应的事件
            extra (dict): 适配器需要的额外参数
        """
        if handle.properties and (keys := handle.properties - event.properties.keys()):
            coros = (self.calls_lib[key](**extra) for key in keys)
            event.properties.update({k: v for k, v in zip(keys, await asyncio.gather(*coros))})
        if result := await handle.func(event):
            await self.sends_lib[result.key](result.data, **extra)
            return handle.block


class Leaf(CloversCore):
    """clovers 响应处理器基类

    Attributes:
        adapter (Adapter): 对接响应的适配器
    """

    adapter: AdapterCore

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.adapter = AdapterCore(name)

    @property
    def info(self):
        return {"name": self.name, "adapter": self.adapter, "plugins": self._plugins}

    def load_adapter(self, name: str | Path, is_path=False):
        """加载 clovers 适配器

        会把目标适配器的方法注册到 self.adapter 中，如有适配器中已有同名方法则忽略

        Args:
            name (str | Path): 适配器的包名或路径
            is_path (bool, optional): 是否为路径
        """
        package = import_name(name, is_path)
        try:
            adapter = getattr(import_module(package), "__adapter__", None)
            assert isinstance(adapter, Adapter)
        except Exception as e:
            logger.exception(f'[{self.name}][loading adapter] "{package}" load failed', exc_info=e)
            return
        logger.info(f'[{self.name}][loading adapter] "{package}" loaded')
        self.adapter.mixin(adapter)

    def load_adapters_from_list(self, adapter_list: list[str]):
        """从包名列表加载适配器

        Args:
            adapter_list (list[str]): 适配器的包名列表
        """
        for adapter in adapter_list:
            self.load_adapter(adapter)

    def load_adapters_from_dirs(self, adapter_dirs: list[str]):
        """从本地目录列表加载适配器

        Args:
            adapter_dirs (list[str]): 适配器的目录列表
        """
        for adapter_dir in adapter_dirs:
            adapter_dir = Path(adapter_dir)
            if not adapter_dir.exists():
                adapter_dir.mkdir(parents=True, exist_ok=True)
                continue
            for adapter in list_modules(adapter_dir):
                self.load_adapter(adapter)

    def plugin_check(self, plugin: Plugin) -> bool:
        check = self.adapter.check_protocol(plugin.protocol)
        if not check:
            logger.warning(f"Plugin({plugin.name}) ignored")
        return check

    def handles_filter(self, handle: BaseHandle) -> bool:
        if method_miss := handle.properties - self.adapter.calls_lib.keys():
            logger.warning(f"Handle ignored: Adapter({self.adapter.name}) is missing required methods: {method_miss}")
            debug_info = {"handle": handle, "method_miss": method_miss}
            logger.debug(repr(debug_info), extra=debug_info)
            return False
        else:
            return True

    async def response_message(self, message: str, /, **extra):
        """响应消息

        Args:
            message (str): 消息内容
            **extra: 额外的参数

        Returns:
            int: 响应数量
        """
        if not message:
            return 0
        count = 0
        temp_event = None
        properties = {}
        for temp_handles, batch_list in self._layers_queue:
            if temp_handles:
                now = time.time()
                alive_handles = [handle for handle in temp_handles if handle.expiration > now]
                temp_handles.clear()
                if alive_handles:
                    temp_event = temp_event or Event(message, [], properties, self.adapter, extra)
                    temp_handles.extend(alive_handles)
                    blocks = await asyncio.gather(*(self.adapter.response(handle, temp_event, extra) for handle in alive_handles))
                    blocks = [block for block in blocks if block is not None]
                    if blocks:
                        blk_p, blk_h = zip(*blocks)
                        count += len(blocks)
                        if any(blk_p):
                            return count
                        elif any(blk_h):
                            continue
            delay_fuse = False
            for handles in batch_list:
                tasklist = (
                    self.adapter.response(handle, Event(message, args, properties, self.adapter, extra), extra)
                    for handle in handles
                    if (args := handle.match(message)) is not None
                )
                blocks = await asyncio.gather(*tasklist)
                blocks = [block for block in blocks if block]
                if blocks:
                    count += len(blocks)
                    if (True, True) in blocks:
                        return count
                    elif (False, True) in blocks:
                        break
                    elif not delay_fuse and (True, False) in blocks:
                        delay_fuse = True
            if delay_fuse:
                break
        return count

    @abstractmethod
    def extract_message(self, **extra) -> str | None:
        """提取消息

        根据传入的事件参数提取消息

        Args:
            **extra: 额外的参数

        Returns:
            Optional[str]: 消息
        """

        raise NotImplementedError

    async def response(self, **extra) -> int:
        """响应事件

        根据传入的事件参数响应事件。

        Args:
            **extra: 额外的参数

        Returns:
            int: 响应数量
        """

        if (message := self.extract_message(**extra)) is not None:
            return await self.response_message(message, **extra)
        else:
            return 0


class Client(CloversCore):
    """clovers 客户端基类

    Attributes:
        running (bool): 客户端运行状态
    """

    def __init__(self) -> None:
        super().__init__()
        self.running = False

    async def startup(self):
        """启动客户端

        如不在 async with 上下文中则要手动调用 startup() 方法，
        """
        if self.running:
            raise RuntimeError("Client is already running")
        self.initialize_plugins()
        tasklist = (asyncio.create_task(coro) for plugin in self.plugins for task in plugin.startup_tasklist if (coro := task()))
        await asyncio.gather(*tasklist)
        self.running = True

    async def shutdown(self):
        """关闭客户端

        如不在 async with 上下文中则要手动调用 shutdown() 方法，
        """
        if not self.running:
            raise RuntimeError("Client is not running")
        tasklist = (asyncio.create_task(coro) for plugin in self.plugins for task in plugin.shutdown_tasklist if (coro := task()))
        await asyncio.gather(*tasklist)
        self.running = False

    async def __aenter__(self) -> None:
        await self.startup()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

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
