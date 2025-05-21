import time
import asyncio
import re
from importlib import import_module
from pathlib import Path
from .utils import import_path
from typing import Any, Callable, Coroutine, Iterable, Sequence
from .typing import Method, MethodLib, Task
from .logger import logger

type HandlerFunction = Callable[[Event], Coroutine[None, None, Result | None]]

type MiddleHandlerFunction = Callable[[Any], Coroutine[None, None, Any | None]]

type PluginCommand = str | Iterable[str] | re.Pattern[str] | None


def kwfilter(func: Method) -> Method:
    """方法参数过滤器"""

    co_argcount = func.__code__.co_argcount
    if co_argcount == 0:
        return lambda *args, **kwargs: func()
    kw = set(func.__code__.co_varnames[:co_argcount])

    async def wrapper(*args, **kwargs):
        return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    return wrapper


class Result:
    """插件响应结果

    Attributes:
        key (str): 响应方法
        data (Any): 响应数据
    """

    def __init__(self, key: str, data) -> None:
        self.key = key
        self.data = data

    def __str__(self) -> str:
        return f"<Result {self.key} {self.data}/>"


class Event:
    """触发响应的事件

    Attributes:
        message (str): 触发插件的消息原文
        args (list[str]): 参数
        properties (dict): 需要的额外属性，由插件声明
        calls (MethodLib): 响应此插件的适配器提供的 call 方法
        extra (dict): 额外数据储存位置，仅在事件链内传递
    """

    calls: MethodLib
    extra: dict

    def __init__(self, message: str, args: Sequence[str], properties: dict):
        self.message = message
        self.args = args
        self.properties = properties

    def call(self, key, *args):
        """执行适配器调用方法，只接受位置参数"""
        return self.calls[key](*args, **self.extra)

    def __str__(self) -> str:
        return f"<Event {self.message}/>"


class BaseHandle:
    """插件任务基类

    Attributes:
        func (Handler): 处理器函数
        properties (set[str]): 声明属性
        block (tuple[bool, bool]): 是否阻止后续插件, 是否阻止后续任务
    """

    def __init__(
        self,
        properties: Iterable[str],
        block: tuple[bool, bool],
        func: HandlerFunction,
    ):
        self.properties = set(properties)
        self.block = block
        self.func = func


class Handle(BaseHandle):
    """指令任务

    Attributes:
        commands (PluginCommands): 触发命令
        priority (int): 任务优先级

        func (Handler): 处理器函数
        properties (set[str]): 声明属性
        block (tuple[bool, bool]): 是否阻止后续插件, 是否阻止后续任务
    """

    def __init__(
        self,
        commands: PluginCommand,
        properties: Iterable[str],
        priority: int,
        block: tuple[bool, bool],
        func: HandlerFunction,
    ):
        super().__init__(properties, block, func)
        self.register(commands)
        self.priority = priority

    def match(self, message: str) -> Sequence[str] | None:
        raise NotImplementedError

    def register(self, command: PluginCommand) -> Iterable[str] | re.Pattern | None:
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
            self.command = "|".join(self.commands)
            self.match = self.match_commands
        else:
            raise TypeError(f"Handle: {command} has an invalid type: {type(command)}")

    def __str__(self) -> str:
        return f"<Handle command='{self.command}' properties='{self.properties}' priority='{self.priority} 'block='{self.block}'/>"

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

        func (Handler): 处理器函数
        properties (set[str]): 声明属性
        block (tuple[bool, bool]): 是否阻止后续插件, 是否阻止后续任务
    """

    def __init__(
        self,
        timeout: float,
        properties: Iterable[str],
        block: tuple[bool, bool],
        func: Callable[[Any, "TempHandle"], Coroutine],
        wrapper: Callable[[MiddleHandlerFunction], HandlerFunction],
    ):
        super().__init__(properties, block, wrapper(lambda e: func(e, self)))
        self.delay(timeout)

    def __str__(self) -> str:
        return f"<TempHandle expiration='{self.expiration}/>"

    def finish(self):
        """结束任务"""
        self.expiration = 0

    def delay(self, timeout: float | int = 30.0):
        """延长任务"""
        self.expiration = timeout + time.time()


class Plugin:
    """插件类

    Attributes:
        name (str, optional): 插件名称. Defaults to "".
        priority (int, optional): 插件优先级. Defaults to 0.
        block (bool, optional): 是否阻止后续任务. Defaults to False.
        build_event (Callable[[Event], Any], optional): 构建事件. Defaults to None.
        build_result (Callable[[Any], Result], optional): 构建结果. Defaults to None.
    """

    def __init__(
        self,
        name: str = "",
        priority: int = 0,
        block: bool = True,
        build_event=None,
        build_result=None,
    ) -> None:

        self.name: str = name
        """插件名称"""
        self.priority: int = priority
        """插件优先级"""
        self.block: bool = block
        """是否阻断后续插件"""
        self.startup_tasklist: list[Task] = []
        """启动任务列表"""
        self.shutdown_tasklist: list[Task] = []
        """关闭任务列表"""
        self.build_event: Callable[[Event], Any] | None = build_event
        """构建event"""
        self.build_result: Callable[[Any], Result] | None = build_result
        """构建result"""
        self.handles: set[Handle] = set()
        """已注册的响应器"""

    def startup(self, func: Task):
        """注册一个启动任务"""
        self.startup_tasklist.append(func)

        return func

    def shutdown(self, func: Task):
        """注册一个结束任务"""
        self.shutdown_tasklist.append(func)

        return func

    class Rule:
        """响应器规则

        Attributes:
            checker (Plugin.Rule.Ruleable): 响应器检查器
        """

        checker: list[Callable[..., bool]]

        type Ruleable = list[Callable[..., bool]] | Callable[..., bool]

        def __init__(self, checker: Ruleable):
            if isinstance(checker, list):
                self.checker = checker
            elif callable(checker):
                self.checker = [checker]
            else:
                raise TypeError(f"Checker: {checker} has an invalid type: {type(checker)}")

        def check(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
            """对函数进行检查装饰"""

            if len(self.checker) == 1:
                checker = self.checker[0]
            else:
                checker = lambda event: all(checker(event) for checker in self.checker)

            async def wrapper(event):
                return await func(event) if checker(event) else None

            return wrapper

    def handle_warpper(self, rule: Rule.Ruleable | Rule | None = None):
        """构建插件的原始event->result响应"""

        def decorator(func: MiddleHandlerFunction) -> HandlerFunction:
            if rule:
                func = rule.check(func) if isinstance(rule, self.Rule) else self.Rule(rule).check(func)
            middle_func = func if (build_event := self.build_event) is None else lambda e: func(build_event(e))
            if not self.build_result:
                return middle_func
            build_result = self.build_result

            async def wrapper(event):
                return build_result(result) if (result := await middle_func(event)) else None

            return wrapper

        return decorator

    def handle(
        self,
        commands: PluginCommand,
        properties: Iterable[str] = [],
        rule: Rule.Ruleable | Rule | None = None,
        priority: int = 0,
        block: bool = True,
    ):
        """注册插件指令响应器

        Args:
            commands (PluginCommands): 指令
            properties (Iterable[str]): 声明需要额外参数
            rule (Rule.Ruleable | Rule | None): 响应规则
            priority (int): 优先级
            block (bool): 是否阻断后续响应器
        """

        def decorator(func: Callable[..., Coroutine]):
            handle = Handle(
                commands,
                properties,
                priority,
                (self.block, block),
                self.handle_warpper(rule)(func),
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
    ):
        """创建插件临时响应器

        Args:
            properties (Iterable[str]): 声明需要额外参数
            timeout (float | int): 临时指令的持续时间
            rule (Rule.Ruleable | Rule | None): 响应规则
            block (bool): 是否阻断后续响应器
        """

        def decorator(func: Callable[..., Coroutine]):
            handle = TempHandle(
                timeout,
                properties,
                (self.block, block),
                func,
                self.handle_warpper(rule),
            )
            self.temp_handles.append(handle)
            return handle.func

        return decorator

    def set_temp_handles(self, temp_handles: list[TempHandle]):
        self.temp_handles = temp_handles

    def __str__(self) -> str:
        lst = [f"<Plugin {self.name}>"]
        for handle in self.handles:
            lst.append(f"\t{handle}")
        if temp_handles := getattr(self, "temp_handles", None):
            for handle in temp_handles:
                lst.append(f"\t{handle}")
        lst.append("/>")
        return "\n".join(lst)


class Adapter:
    """响应器类

    Attributes:
        name (str, optional): 响应器名称. Defaults to "".
        properties_lib (MethodLib): 获取参数方法库
        sends_lib (MethodLib): 发送消息方法库
        calls_lib (MethodLib): 调用方法库
    """

    def __init__(self, name: str = "") -> None:
        self.name: str = name
        self.properties_lib: MethodLib = {}
        self.sends_lib: MethodLib = {}
        self.calls_lib: MethodLib = {}

    def property_method(self, method_name: str):
        """添加一个获取参数方法"""

        def decorator(func: Method):
            method = kwfilter(func)
            if method_name not in self.calls_lib:
                self.calls_lib[method_name] = method
            self.properties_lib[method_name] = method
            return func

        return decorator

    def send_method(self, method_name: str):
        """添加一个发送消息方法"""

        def decorator(func: Method):
            method = kwfilter(func)
            if method_name not in self.calls_lib:
                self.calls_lib[method_name] = method
            self.sends_lib[method_name] = method
            return func

        return decorator

    def call_method(self, method_name: str):
        """添加一个调用方法"""

        def decorator(func: Method):
            self.calls_lib[method_name] = kwfilter(func)
            return func

        return decorator

    def send(self, result: Result, **extra):
        """执行适配器发送方法"""
        return self.sends_lib[result.key](result.data, **extra)

    def property(self, key, **extra):
        """执行适配器获取属性方法"""
        return self.properties_lib[key](**extra)

    def update(self, adapter: "Adapter"):
        """更新兼容方法"""
        self.properties_lib.update(adapter.properties_lib)
        self.sends_lib.update(adapter.sends_lib)
        self.calls_lib.update(adapter.calls_lib)

    def remix(self, adapter: "Adapter"):
        """混合其他兼容方法"""
        for k, v in adapter.properties_lib.items():
            self.properties_lib.setdefault(k, v)
        for k, v in adapter.sends_lib.items():
            self.sends_lib.setdefault(k, v)
        for k, v in adapter.calls_lib.items():
            self.calls_lib.setdefault(k, v)

    async def response(self, handle: BaseHandle, event: Event, extra: dict):
        """使用适配器响应任务

        Args:
            handle (BaseHandle): 触发的插件任务
            event (Event): 触发响应的事件
            extra (dict): 适配器需要的额外参数
        """
        if handle.properties:
            keys = list(handle.properties - event.properties.keys())
            coros = [self.property(key, **extra) for key in keys]
            event.properties.update({k: v for k, v in zip(keys, await asyncio.gather(*coros))})
        if result := await handle.func(event):
            await self.send(result, **extra)
            return handle.block

    def __str__(self) -> str:
        lst = [f"<Adapter {self.name}>"]
        for method_name in self.sends_lib.keys():
            lst.append(f"\t<SendMethod {method_name}\n>")
        for method_name in self.calls_lib.keys():
            lst.append(f"\t<CallMethod {method_name}\n>")
        for method_name in self.properties_lib.keys():
            lst.append(f"\t<PropertyMethod {method_name}\n>")
        lst.append("/>")
        return "\n".join(lst)


class CloversCore:
    """四叶草核心

    此处管理插件的加载和准备，是各种实现的基础

    Attributes:
        name (str): 项目名
        plugins (list[Plugin]): 项目管理的插件列表
    """

    name: str = "CloversObject"

    @property
    def plugins(self):
        return (plugin for plugin in self._plugins)

    @plugins.setter
    def plugins(self, plugins: Iterable[Plugin]):
        if self._ready:
            raise RuntimeError("cannot set plugins after ready")
        self._plugins.clear()
        self._plugins.extend(plugins)

    def __init__(self):
        self._plugins: list[Plugin] = []
        """插件优先级和插件列表"""
        self._handles_queue: list[tuple[list[TempHandle], list[list[Handle]]]] = []
        """已注册响应器队列"""
        self._ready: bool = False
        """插件是否就绪"""

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
            self._handles_queue.append((_temp_handles[key], [_sub_handles[k] for k in sub_keys]))
        self._ready = True
