import abc
import time
import asyncio
import re
from pathlib import Path
from importlib import import_module
from .utils import import_path
from typing import cast, runtime_checkable, Any, Protocol, Literal
from collections.abc import Callable, Coroutine, Iterable, Sequence
from .protocol import check_compatible
from .logger import logger


type AdapterMethod = Callable[..., Coroutine[None, Any, Any]]
type AdapterMethodLib = dict[str, AdapterMethod]
type Task = Callable[[], Coroutine[None, Any, Any]]
type PluginCommand = str | Iterable[str] | re.Pattern[str] | None
type EventHandler = Callable[[Event], Coroutine[None, Any, Result | None]]
type RawEventHandler = Callable[[Any], Coroutine[None, Any, Any | None]]
type RawTempEventHandler = Callable[[Any, TempHandle], Coroutine[None, Any, Any | None]]
type EventBuilder = Callable[[Event], Any]
type ResultBuilder = Callable[[Any], Result | None]


def kwfilter(func: AdapterMethod) -> AdapterMethod:
    """方法参数过滤器"""

    co_argcount = func.__code__.co_argcount
    if co_argcount == 0:
        return lambda *args, **kwargs: func()
    kw = set(func.__code__.co_varnames[:co_argcount])

    async def wrapper(*args, **kwargs):
        return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    return wrapper


@runtime_checkable
class EventProtocol(Protocol):
    """事件协议
    经过 EventBuilder 处理构建的返回值需要满足 EventProtocol 协议

    Attributes:
        message (str): 触发插件的消息原文
        args (Sequence[str]): 指令参数
        properties (dict): 插件声明的属性
    Methods:
        call(key: str, *args): 执行适配器调用方法并获取返回值
    """

    message: str
    """触发插件的消息原文"""
    args: Sequence[str]
    """指令参数"""
    properties: dict
    """插件声明的属性"""

    def call(self, key: str, *args): ...


class Info(abc.ABC):

    @property
    @abc.abstractmethod
    def info(self) -> dict[str, Any]:
        """信息"""
        raise NotImplementedError

    def __repr__(self) -> str:
        return repr({self.__class__.__name__: self.info})


class Result(Info):
    """插件响应结果

    Attributes:
        key (str): 响应方法
        data (Any): 响应数据
    """

    def __init__(self, key: str, data) -> None:
        self.key = key
        self.data = data

    @property
    def info(self):
        return {"key": self.key, "data": self.data}


class Event(Info):
    """触发响应的事件

    Attributes:
        message (str): 触发插件的消息原文
        args (list[str]): 指令参数
        properties (dict): 需要的额外属性，由插件声明

    Methods:
        call (key: str, *args): 执行适配器调用方法并获取返回值
    """

    def __init__(self, message: str, args: Sequence[str], properties: dict, calls_lib: AdapterMethodLib, extra: dict):
        self.message = message
        self.args = args
        self.properties = properties
        self._calls_lib = calls_lib
        self._extra = extra

    @property
    def info(self) -> dict:
        return {"message": self.message, "args": self.args}

    def call(self, key: str, *args):
        """执行适配器调用方法，只接受位置参数"""
        return self._calls_lib[key](*args, **self._extra)

    def __getattr__(self, name: str):
        try:
            return self.properties[name]
        except KeyError:
            raise AttributeError(f"Event object has no attribute '{name}'")


class BaseHandle(Info):
    """插件任务基类

    Attributes:
        func (EventHandler): 处理器函数
        properties (set[str]): 声明属性
        block (tuple[bool, bool]): 是否阻止后续插件, 是否阻止后续任务
    """

    def __init__(
        self,
        properties: Iterable[str],
        block: tuple[bool, bool],
        func: EventHandler,
    ):
        self.properties = set(properties)
        self.block = block
        self.func = func


class Handle(BaseHandle):
    """指令任务

    Attributes:
        command (PluginCommand): 触发命令
        priority (int): 任务优先级

        func (EventHandler): 处理器函数
        properties (set[str]): 声明属性
        block (tuple[bool, bool]): 是否阻止后续插件, 是否阻止后续任务
    """

    def __init__(
        self,
        command: PluginCommand,
        properties: Iterable[str],
        priority: int,
        block: tuple[bool, bool],
        func: EventHandler,
    ):
        super().__init__(properties, block, func)
        self.register(command)
        self.priority = priority

    @property
    def info(self):
        return {"command": self.command, "properties": self.properties, "priority": self.priority, "block": self.block}

    def match(self, message: str) -> Sequence[str] | None:
        """匹配指令

        Args:
            message (str): 待匹配的消息

        Returns:
            Oprtional[Sequence[str]]: 如果匹配到则返回从 message 提取的参数，如果没有匹配则返回 None
        """
        raise NotImplementedError

    def register(self, command: PluginCommand) -> Iterable[str] | re.Pattern | None:
        """注册指令

        Args:
            command (PluginCommand): 命令
        """

        if not command:
            self.command = ""
            self.match = self.match_none
        elif isinstance(command, str):
            self.patttrn = re.compile(command)
            self.command = self.patttrn.pattern
            self.match = self.match_regex
        elif isinstance(command, re.Pattern):
            self.patttrn = command
            self.command = self.patttrn.pattern
            self.match = self.match_regex
        elif isinstance(command, Iterable):
            self.commands = sorted(set(command), key=lambda x: len(x))
            self.command = repr(self.commands)
            self.match = self.match_commands
        else:
            raise TypeError(f"Handle: {command} has an invalid type: {type(command)}")

    @staticmethod
    def match_none(message: str):
        return message.split()

    def match_regex(self, message: str):
        if args := self.patttrn.match(message):
            return args.groups()

    def match_commands(self, message: str):
        for command in self.commands:
            if message.startswith(command):
                return message.lstrip(command).split()


class TempHandle(BaseHandle):
    """临时任务

    Attributes:
        timeout (float): 超时时间
        func (EventHandler): 处理器函数
        properties (set[str]): 声明属性
        block (tuple[bool, bool]): 是否阻止后续插件, 是否阻止后续任务
    """

    def __init__(
        self,
        timeout: float,
        properties: Iterable[str],
        block: tuple[bool, bool],
        func: RawTempEventHandler,
        wrapper: Callable[[RawEventHandler], EventHandler],
        state: Any | None = None,
    ):
        super().__init__(properties, block, wrapper(lambda e: func(e, self)))
        self.state = state
        self.delay(timeout)

    @property
    def info(self):
        return {"expiration": self.expiration, "properties": self.properties, "block": self.block}

    def finish(self):
        """结束任务"""
        self.expiration = 0

    def delay(self, timeout: float | int = 30.0):
        """延长任务"""
        self.expiration = timeout + time.time()


class Plugin(Info):
    """插件类

    Attributes:
        name (str, optional): 插件名称. Defaults to "".
        priority (int, optional): 插件优先级. Defaults to 0.
        block (bool, optional): 是否阻止后续任务. Defaults to False.
        build_event (EventBuilder, optional): 构建事件. Defaults to None.
        build_result (ResultBuilder, optional): 构建结果. Defaults to None.
        handles (set[Handle]): 已注册的响应器
        protocol (CloversProtocol): 同名类型协议
    """

    def __init__(
        self,
        name: str = "",
        priority: int = 0,
        block: bool = True,
        build_event: EventBuilder | None = None,
        build_result: ResultBuilder | None = None,
    ) -> None:

        self.name: str = name
        """插件名称"""
        self.priority: int = priority
        """插件优先级"""
        self.block: bool = block
        """是否阻断后续插件"""
        self.build_event = build_event
        """构建event"""
        self.build_result = build_result
        """构建result"""
        self.startup_tasklist: list[Task] = []
        """启动任务列表"""
        self.shutdown_tasklist: list[Task] = []
        """关闭任务列表"""
        self.handles: set[Handle] = set()
        """已注册的响应器"""
        self.protocol: dict[str, dict[str, Any] | None] = {"properties": None, "sends": None, "calls": None}
        """协议"""
        self.require_plugins: list[str] = []
        """依赖的插件"""

    @property
    def info(self):
        return {"name": self.name, "priority": self.priority, "block": self.block, "handles": self.handles}

    def set_protocol(self, key: Literal["properties", "sends", "calls"], data: type):
        """设置插件类型协议

        Args:
            key (Literal["properties", "sends", "calls"]): 协议位置
            data (type): 协议类型，包含字段和声明的类型
        """

        if key not in self.protocol:
            raise KeyError(f"{self.name} has no protocol key: {key}")
        self.protocol[key] = {k: v for k, v in data.__annotations__.items() if not k.startswith("_")}

    def require(self, plugin_name: str):
        """声明依赖的插件

        Args:
            plugin_name (str): 插件名称
        """
        self.require_plugins.append(plugin_name)

    def startup(self, func: Task):
        """注册一个启动任务"""
        self.startup_tasklist.append(func)

        return func

    def shutdown(self, func: Task):
        """注册一个结束任务"""
        self.shutdown_tasklist.append(func)

        return func

    class Rule:
        """响应器规则"""

        type Checker[PluginEvent] = Callable[[PluginEvent], bool]
        type Ruleable = Checker | list[Checker]

        def __init__(self, rule: Ruleable):
            if callable(rule):
                self._checker = [rule]
            elif isinstance(rule, list) and all(map(callable, rule)):
                self._checker = rule
            else:
                raise TypeError("checker must be callable or list[callable]")

        def check(self, func: RawEventHandler) -> RawEventHandler:
            """对函数进行检查装饰"""
            if not self._checker:
                return func
            if len(self._checker) == 1:
                _checker = self._checker[0]
            else:
                _checker = lambda event: all(checker(event) for checker in self._checker)

            async def wrapper(event):
                return await func(event) if _checker(event) else None

            return wrapper

    def handle_wrapper(self, rule: Rule.Ruleable | Rule | None = None):
        """构建插件的原始event->result响应"""

        def decorator(func: RawEventHandler) -> EventHandler:
            if rule:
                func = rule.check(func) if isinstance(rule, self.Rule) else self.Rule(rule).check(func)
            middle_func = func if (build_event := self.build_event) is None else lambda e: func(build_event(e))
            if not self.build_result:
                return cast(EventHandler, middle_func)
            build_result = self.build_result

            async def wrapper(event):
                return build_result(result) if (result := await middle_func(event)) else None

            return wrapper

        return decorator

    def handle(
        self,
        command: PluginCommand,
        properties: Iterable[str] = [],
        rule: Rule.Ruleable | Rule | None = None,
        priority: int = 0,
        block: bool = True,
    ):
        """注册插件指令响应器

        Args:
            command (PluginCommand): 指令
            properties (Iterable[str]): 声明需要额外参数
            rule (Rule.Ruleable | Rule | None): 响应规则
            priority (int): 优先级
            block (bool): 是否阻断后续响应器
        """

        def decorator(func: RawEventHandler):
            handle = Handle(
                command,
                properties,
                priority,
                (self.block, block),
                self.handle_wrapper(rule)(func),
            )
            self.handles.add(handle)
            return handle.func

        return decorator

    def temp_handle(
        self,
        properties: Iterable[str] = [],
        timeout: float | int = 30.0,
        rule: Rule.Ruleable | Rule | None = None,
        block: bool = True,
        state: Any | None = None,
    ):
        """创建插件临时响应器

        Args:
            properties (Iterable[str]): 声明需要额外参数
            timeout (float | int): 临时指令的持续时间
            rule (Rule.Ruleable | Rule | None): 响应规则
            block (bool): 是否阻断后续响应器
            state (Any | None): 传递给临时指令的额外参数
        """

        def decorator(func: RawTempEventHandler):
            handle = TempHandle(
                timeout,
                properties,
                (self.block, block),
                func,
                self.handle_wrapper(rule),
                state,
            )
            self.temp_handles.append(handle)
            return handle.func

        return decorator

    def set_temp_handles(self, temp_handles: list[TempHandle]):
        self.temp_handles = temp_handles


class Adapter(Info):
    """响应器类

    Attributes:
        name (str, optional): 响应器名称. Defaults to "".
        properties_lib (AdapterMethodLib): 获取参数方法库
        sends_lib (AdapterMethodLib): 发送消息方法库
        calls_lib (AdapterMethodLib): 调用方法库
        protocol (CloversProtocol): 同名类型协议
    """

    def __init__(self, name: str = "") -> None:
        self.name: str = name
        self.properties_lib: AdapterMethodLib = {}
        self.sends_lib: AdapterMethodLib = {}
        self.calls_lib: AdapterMethodLib = {}
        self.protocol: dict[str, dict[str, Any] | None] = {"properties": None, "sends": None, "calls": None}

    @property
    def info(self):
        return {
            "name": self.name,
            "SendMethodLib": list(self.sends_lib.keys()),
            "PropertyMethodLib": list(self.properties_lib.keys()),
            "CallMethodLib": list(self.calls_lib.keys()),
        }

    def set_protocol(self, key: Literal["properties", "sends", "calls"], data: type):
        """设置适配器类型协议

        Args:
            key (Literal["properties", "sends", "calls"]): 协议位置
            data (type): 协议类型，包含字段和声明的类型
        """

        if key not in self.protocol:
            raise KeyError(f"{self.name} has no protocol key: {key}")
        self.protocol[key] = {k: v for k, v in data.__annotations__.items() if not k.startswith("_")}

    def property_method(self, method_name: str):
        """添加一个获取参数方法"""

        def decorator(func: AdapterMethod):
            method = kwfilter(func)
            if method_name not in self.calls_lib:
                self.calls_lib[method_name] = method
            self.properties_lib[method_name] = method
            if self.protocol["properties"] is None:
                self.protocol["properties"] = {}
            if annot := func.__annotations__.get("return"):
                self.protocol["properties"][method_name] = annot
            return func

        return decorator

    def send_method(self, method_name: str):
        """添加一个发送消息方法"""

        def decorator(func: AdapterMethod):
            method = kwfilter(func)
            if method_name not in self.calls_lib:
                self.calls_lib[method_name] = method
            self.sends_lib[method_name] = method
            if self.protocol["sends"] is None:
                self.protocol["sends"] = {}
            name = func.__code__.co_varnames[0]
            if annot := func.__annotations__.get(name):
                self.protocol["sends"][method_name] = annot
            return func

        return decorator

    def call_method(self, method_name: str):
        """添加一个调用方法"""

        def decorator(func: AdapterMethod):
            self.calls_lib[method_name] = kwfilter(func)
            co_posonlyargcount = func.__code__.co_posonlyargcount
            if co_posonlyargcount > 0:
                names = func.__code__.co_varnames[:co_posonlyargcount]
                fields = func.__annotations__
                if all(name in fields for name in names) and "return" in fields:
                    if self.protocol["calls"] is None:
                        self.protocol["calls"] = {}
                    self.protocol["calls"][method_name] = Callable[[fields[name] for name in names], fields["return"]]
            return func

        return decorator

    def update(self, adapter: "Adapter"):
        """更新兼容方法"""
        self.properties_lib.update(adapter.properties_lib)
        self.sends_lib.update(adapter.sends_lib)
        self.calls_lib.update(adapter.calls_lib)
        for k in ["properties", "sends", "calls"]:
            if (self_fields := self.protocol[k]) is None:
                if (adapter_fields := adapter.protocol[k]) is None:
                    continue
                self.protocol[k] = adapter_fields.copy()
            elif (adapter_fields := adapter.protocol[k]) is None:
                continue
            else:
                self_fields.update(adapter_fields)

    def remix(self, adapter: "Adapter"):
        """混合其他兼容方法"""
        for k, v in adapter.properties_lib.items():
            self.properties_lib.setdefault(k, v)
        for k, v in adapter.sends_lib.items():
            self.sends_lib.setdefault(k, v)
        for k, v in adapter.calls_lib.items():
            self.calls_lib.setdefault(k, v)
        for k in ["properties", "sends", "calls"]:
            if (self_fields := self.protocol[k]) is None:
                if (adapter_fields := adapter.protocol[k]) is None:
                    continue
                self.protocol[k] = adapter_fields.copy()
            elif (adapter_fields := adapter.protocol[k]) is None:
                continue
            else:
                for key, value in adapter_fields.items():
                    self_fields.setdefault(key, value)

    def send(self, result: Result, **extra):
        """执行适配器发送方法"""
        return self.sends_lib[result.key](result.data, **extra)

    async def response(self, handle: BaseHandle, event: Event, extra: dict):
        """使用适配器响应任务

        Args:
            handle (BaseHandle): 触发的插件任务
            event (Event): 触发响应的事件
            extra (dict): 适配器需要的额外参数
        """
        if handle.properties and (keys := handle.properties - event.properties.keys()):
            keys = list(keys)
            coros = (self.properties_lib[key](**extra) for key in keys)
            event.properties.update({k: v for k, v in zip(keys, await asyncio.gather(*coros))})
        if result := await handle.func(event):
            await self.send(result, **extra)
            return handle.block


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
        if is_path or isinstance(name, Path):
            import_name = import_path(name)
        else:
            import_name = name.replace("-", "_")
        try:
            plugin = getattr(import_module(import_name), "__plugin__", None)
            assert isinstance(plugin, Plugin)
        except Exception as e:
            logger.exception(f'[{self.name}][loading plugin] "{import_name}" load failed', exc_info=e)
            return
        key = plugin.name or import_name
        if plugin in self._plugins:
            return
        if plugin.require_plugins:
            for require_plugin in plugin.require_plugins:
                self.load_plugin(require_plugin)
        logger.info(f'[{self.name}][loading plugin] "{import_name}" loaded')
        plugin.name = key
        self._plugins.append(plugin)

    def handles_filter(self, handle: BaseHandle) -> bool:
        """任务过滤器

        Args:
            handle (Handle): 响应任务

        Returns:
            bool: 是否通过过滤
        """
        return True

    def plugins_filter(self, plugin: Plugin) -> bool:
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
        self._plugins = [plugin for plugin in self._plugins if self.plugins_filter(plugin)]
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


class Leaf(CloversCore):
    """clovers 响应处理器基类

    Attributes:
        adapter (Adapter): 对接响应的适配器
    """

    adapter: Adapter

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.adapter = Adapter(name)

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

        if is_path or isinstance(name, Path):
            import_name = import_path(name)
        else:
            import_name = name.replace("-", "_")
        try:
            adapter = getattr(import_module(import_name), "__adapter__", None)
            assert isinstance(adapter, Adapter)
        except Exception as e:
            logger.exception(f'[{self.name}][loading adapter] "{import_name}" load failed', exc_info=e)
            return
        logger.info(f'[{self.name}][loading adapter] "{import_name}" loaded')
        self.adapter.update(adapter)

    def plugins_filter(self, plugin: Plugin) -> bool:
        plugin_protocol = plugin.protocol
        adapter_protocol = self.adapter.protocol
        for k in ["properties", "sends", "calls"]:
            if (adapter_fields := adapter_protocol[k]) is None or (plugin_fields := plugin_protocol[k]) is None:
                continue
            keys = plugin_fields.keys() & adapter_fields.keys()
            for key in keys:
                if not check_compatible(adapter_fields[key], plugin_fields[key]):
                    logger.warning(
                        f"Plugin({plugin.name}) ignored: "
                        f"plugin '{k}' method '{key}' requires type '{plugin_fields[key]}', "
                        f"but Adapter({self.adapter.name}) provides '{adapter_fields[key]}'."
                    )
                    return False
        return True

    def handles_filter(self, handle: BaseHandle) -> bool:
        if method_miss := handle.properties - self.adapter.properties_lib.keys():
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
        calls_lib = self.adapter.calls_lib
        for temp_handles, batch_list in self._layers_queue:
            if temp_handles:
                now = time.time()
                alive_handles = [handle for handle in temp_handles if handle.expiration > now]
                temp_handles.clear()
                if alive_handles:
                    temp_event = temp_event or Event(message, [], properties, calls_lib, extra)
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
                    self.adapter.response(handle, Event(message, args, properties, calls_lib, extra), extra)
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

    @abc.abstractmethod
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
        tasklist = (asyncio.create_task(task()) for plugin in self.plugins for task in plugin.startup_tasklist)
        await asyncio.gather(*tasklist)
        self.running = True

    async def shutdown(self):
        """关闭客户端

        如不在 async with 上下文中则要手动调用 shutdown() 方法，
        """
        if not self.running:
            raise RuntimeError("Client is not running")
        tasklist = (asyncio.create_task(task()) for plugin in self.plugins for task in plugin.shutdown_tasklist)
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
