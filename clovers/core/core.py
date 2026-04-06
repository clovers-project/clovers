import asyncio
from abc import abstractmethod
from collections.abc import Iterable, Callable
from pathlib import Path
from importlib import import_module
from .utils import list_modules
from .protocol import protocol_format, check_compatible, is_coro
from ..base import Coro, Info, Adapter, AdapterMethod, BaseHandle, Event
from ..plugin import Handle, TempHandle, Plugin
from ..logger import logger


class ImportCore[T]:
    def __init__(self, __attrs: list[str], __type: type[T], log_header: str = ""):
        self.log_header = log_header if log_header else "[ImportCore]"
        self.__attrs = __attrs
        self.__type = __type

    def load(self, package: str):
        try:
            module = import_module(package)
        except ImportError:
            logger.exception(f'{self.log_header} Module "{package}" not found')
            return
        except Exception as e:
            logger.exception(f'{self.log_header} "{package}" load failed', exc_info=e)
            return
        attr_name = next((x for x in self.__attrs if hasattr(module, x)), None)
        if attr_name is None:
            logger.error(f'{self.log_header} Module "{package}" missing attribute "{self.__attrs}"')
            return
        attr = getattr(module, attr_name)
        if not isinstance(attr, self.__type):
            logger.error(f'{self.log_header} "{package}.{attr_name}" is type {type(attr)}, expected {self.__type}')
            return
        return attr

    def load_from_list(self, import_list: Iterable[str]):
        """从包名列表加载"""
        for name in import_list:
            self.load(name.replace("-", "_"))

    def load_from_dirs(self, import_dirs: Iterable[str]):
        """从本地目录列表加载"""
        for import_dir in import_dirs:
            dir = Path(import_dir)
            if not dir.exists():
                continue
            self.load_from_list(list_modules(dir))


class AdapterCore(Adapter, ImportCore[Adapter]):
    def __init__(self, name: str) -> None:
        Adapter.__init__(self, name)
        ImportCore.__init__(self, ["ADAPTER", "adapter", "__adapter__"], Adapter, f"[{self.name}][loading adapter]")
        self.__protocol = {"send": {}, "call": {}}

    def check_protocol(self, protocol: type | None):
        """检查适配器类型协议

        Args:
            data (type): 事件协议类型，包含字段和声明的类型
        """
        if protocol is None:
            return True
        check_protocol = protocol_format(protocol)
        for k in ["send", "call"]:
            if (self_fields := self.__protocol[k]) and (check_fields := check_protocol[k]):
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
            if annot := func.__annotations__.get("return"):
                self.__protocol["call"][method_name] = annot
        else:
            names = func.__code__.co_varnames[:co_posonlyargcount]
            fields = func.__annotations__
            if all(name in fields for name in names) and "return" in fields:
                if is_coro(func):
                    self.__protocol["call"][method_name] = Callable[[fields[name] for name in names], Coro[fields["return"]]]
                else:
                    self.__protocol["call"][method_name] = Callable[[fields[name] for name in names], fields["return"]]
        self.calls_lib[method_name] = func
        return func

    async def invoke_handler(self, handle: BaseHandle, event: Event, extra: dict):
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

    def load_adapter(self, adapter_list: list[str] | None = None, adapter_dirs: list[str] | None = None):
        """加载 clovers 适配器

        会把目标适配器的方法注册到 self 中，如已有同名方法则忽略

        Args:
            adapter_list (list[str]): 适配器的包名列表
            adapter_dirs (list[str]): 适配器的目录列表
        """
        if adapter_list:
            self.load_from_list(adapter_list)
        if adapter_dirs:
            self.load_from_dirs(adapter_dirs)

    def load(self, package: str):
        adapter = super().load(package)
        if adapter:
            self.mixin(adapter)
            adapter.name = adapter.name or package
            logger.info(f'{self.log_header} "{adapter.name}" loaded')


class PluginCore(Info, ImportCore[Plugin]):
    """插件核心

    此处管理插件的加载和准备

    Attributes:
        name (str): 项目名
        plugins (list[Plugin]): 项目管理的插件列表
    """

    def __init__(self, name: str = ""):
        self.name = name
        ImportCore.__init__(self, ["PLUGIN", "plugin", "__plugin__"], Plugin, f"[{self.name}][loading plugin]")
        self._plugins: list[Plugin] = []

    @property
    def info(self):
        return {"name": self.name, "plugins": self._plugins}

    def __iter__(self):
        yield from self._plugins

    def load_plugin(self, plugin_list: list[str] | None = None, plugin_dirs: list[str] | None = None):
        """加载 clovers 插件

        Args:
            plugin_list (list[str]): 插件的包名列表
            plugin_dirs (list[str]): 插件的目录列表
        """
        if plugin_list:
            self.load_from_list(plugin_list)
        if plugin_dirs:
            self.load_from_dirs(plugin_dirs)

    def load(self, package: str):
        plugin = super().load(package)
        if (plugin is None) or (plugin in self._plugins):
            return
        if plugin.require_plugins:
            self.load_from_list(plugin.require_plugins)
        plugin.name = plugin.name or package
        self._plugins.append(plugin)
        logger.info(f'{self.log_header} "{plugin.name}" loaded')


class CloversCoreInterface(Info):
    """clovers 适配器基类"""

    @abstractmethod
    async def startup(self): ...
    @abstractmethod
    async def shutdown(self): ...

    @abstractmethod
    def dispatch(self, **extra) -> None: ...

    async def __aenter__(self):
        await self.startup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.shutdown()


class CloversCore(CloversCoreInterface):
    """clovers 响应处理器基类

    Args:
        name (str): 项目名
        temp_handles (dict[int, list[TempHandle]], optional): 临时响应器存储位置. Defaults to {}.
    """

    adapter: AdapterCore
    plugins: PluginCore

    type HandleBatch = list[Handle]
    """同优先级的响应器组"""
    type TempHandleBatchs = list[set[TempHandle]]
    """同优先级的临时响应器组"""
    type HandleBatchQueue = list[HandleBatch]
    """按响应优先级排序的响应器组队列"""
    type HandleLayer = tuple[TempHandleBatchs, HandleBatchQueue]
    """插件同一优先级下的响应器层"""

    def __init__(self, name: str) -> None:

        self.adapter = AdapterCore(name)
        self.plugins = PluginCore(name)
        self._layers_queue: list[CloversCore.HandleLayer] = []
        self._ready: bool = False
        self._tasks: set[asyncio.Task] = set()
        self._temp_handles: dict[int, CloversCore.TempHandleBatchs] = {}

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def info(self):
        return {"adapter": self.adapter.info, "plugins": self.plugins.info}

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

    async def startup(self):
        """启动 clovers 核心"""
        if self._ready:
            raise RuntimeError("Client is already running")
        self._ready = True
        _handles: dict[int, list[Handle]] = {}
        _plugins = [plugin for plugin in self.plugins if self.plugin_check(plugin)]
        for plugin in _plugins:
            self._temp_handles.setdefault(plugin.priority, []).append(plugin.temp_handles)
            _handles.setdefault(plugin.priority, []).extend(plugin)
        for key in sorted(_handles.keys()):
            _sub_handles: dict[int, list[Handle]] = {}
            for handle in _handles[key]:
                if self.handles_filter(handle):
                    _sub_handles.setdefault(handle.priority, []).append(handle)
            sub_keys = sorted(_sub_handles.keys())
            self._layers_queue.append((self._temp_handles[key], [_sub_handles[k] for k in sub_keys]))
        tasks = [task for plugin in self.plugins for task in plugin.run_startup()]
        if tasks:
            await asyncio.gather(*tasks)
        self.dispatch = self._dispatch_active

    async def shutdown(self):
        """关闭 clovers 核心"""
        if not self._ready:
            raise RuntimeError("Client is not running")
        self.dispatch = self._dispatch_inactive
        if self._tasks:
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._layers_queue.clear()
        tasks = [task for plugin in self.plugins for task in plugin.run_shutdown()]
        if tasks:
            await asyncio.gather(*tasks)
        self._ready = False

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
        for temp_batchs, batch_list in self._layers_queue:
            temp_handles = [handle for batch in temp_batchs for handle in batch]
            if temp_handles:
                temp_event = temp_event or Event(message, [], properties, self.adapter, extra)
                blocks = await asyncio.gather(*(self.adapter.invoke_handler(handle, temp_event, extra) for handle in temp_handles))
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
                    self.adapter.invoke_handler(handle, Event(message, args, properties, self.adapter, extra), extra)
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

    def create_task(self, coro: Coro):
        self._tasks.add(task := asyncio.create_task(coro))
        task.add_done_callback(self._tasks.discard)

    def dispatch(self, **extra) -> None:
        """响应事件

        根据传入的事件参数响应事件。

        Args:
            **extra: 额外的参数
        """
        raise RuntimeError("You must call 'await startup()' before dispatching events.")

    def _dispatch_inactive(self, **extra): ...

    def _dispatch_active(self, **extra):

        if (message := self.extract_message(**extra)) is not None:
            self.create_task(self.response_message(message, **extra))
            return


class CloversMultCore(CloversCoreInterface):
    """多核 clovers 框架"""

    def __init__(self, *cores: CloversCore):
        if any(core.is_ready for core in cores):
            raise RuntimeError("Cannot combine ready cores")
        self.cores = cores

    @property
    def info(self):
        return {i: core.info for i, core in enumerate(self.cores)}

    async def startup(self):
        await asyncio.gather(*(core.startup() for core in self.cores))

    async def shutdown(self):
        await asyncio.gather(*(core.shutdown() for core in self.cores))

    @abstractmethod
    def locate_core(self, **extra) -> CloversCore | None: ...

    def dispatch(self, **extra) -> None:
        core = self.locate_core(**extra)
        if core is not None:
            core.dispatch(**extra)
