import time
import re
from typing import Any
from collections.abc import Callable, Iterable, Sequence
from .base import Coro, Task, Info, Event, Result, EventHandler, BaseHandle

type Matchable = str | Iterable[str] | re.Pattern[str] | None
type RawEventHandler = Callable[[Any], Coro[Any | None]]
type RawTempEventHandler = Callable[[Any, TempHandle], Coro[Any | None]]

type EventBuilder = Callable[[Event], Any]
type ResultBuilder = Callable[[Any], Result | None]


class Handle(BaseHandle):
    """指令任务

    Attributes:
        command (Matchable): 触发命令
        properties (set[str]): 声明属性
        priority (int): 任务优先级
        block (tuple[bool, bool]): 是否阻止后续插件, 是否阻止后续任务
        func (EventHandler): 处理器函数
    """

    def __init__(
        self,
        command: Matchable,
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

    def register(self, command: Matchable) -> Iterable[str] | re.Pattern | None:
        """注册指令

        Args:
            command (Matchable): 命令
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
        func: EventHandler,
        state: Any | None = None,
    ):
        super().__init__(properties, block, func)
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


class Plugin[EventType](Info):
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
        self.require_plugins: set[str] = set()
        """依赖的插件"""
        self.protocol: type | None = None

    @property
    def info(self):
        return {"name": self.name, "priority": self.priority, "block": self.block, "handles": self.handles}

    def require(self, plugin_name: str):
        """声明依赖的插件

        Args:
            plugin_name (str): 插件名称
        """
        self.require_plugins.add(plugin_name)

    def startup(self, func: Task):
        """注册一个启动任务"""
        self.startup_tasklist.append(func)

        return func

    def shutdown(self, func: Task):
        """注册一个结束任务"""
        self.shutdown_tasklist.append(func)

        return func

    class Rule[T]:
        """响应器规则"""

        type Checker = Callable[[T], bool]
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
                return middle_func
            build_result = self.build_result

            async def wrapper(event):
                return build_result(result) if (result := await middle_func(event)) else None

            return wrapper

        return decorator

    def handle(
        self,
        command: Matchable,
        properties: Iterable[str] = [],
        rule: Rule[EventType].Ruleable | Rule[EventType] | None = None,
        priority: int = 0,
        block: bool | tuple[bool, bool] = True,
    ):
        """注册插件指令响应器

        Args:
            command (Matchable): 指令
            properties (Iterable[str]): 声明需要额外参数
            rule (Rule.Ruleable | Rule | None): 响应规则
            priority (int): 优先级
            block (bool | tuple[bool, bool]): 是否阻断后续响应器
        """

        def decorator(func: RawEventHandler):
            handle = Handle(
                command,
                properties,
                priority,
                (self.block, block) if isinstance(block, bool) else block,
                self.handle_wrapper(rule)(func),
            )
            self.handles.add(handle)
            return handle.func

        return decorator

    def temp_handle(
        self,
        properties: Iterable[str] = [],
        timeout: float | int = 30.0,
        rule: Rule[EventType].Ruleable | Rule[EventType] | None = None,
        block: bool | tuple[bool, bool] = True,
        state: Any | None = None,
    ):
        """创建插件临时响应器

        Args:
            properties (Iterable[str]): 声明需要额外参数
            timeout (float | int): 临时指令的持续时间
            rule (Rule.Ruleable | Rule | None): 响应规则
            block (bool | tuple[bool, bool]): 是否阻断后续响应器
            state (Any | None): 传递给临时指令的额外参数
        """

        def decorator(func: RawTempEventHandler):
            handle = TempHandle(
                timeout,
                properties,
                (self.block, block) if isinstance(block, bool) else block,
                self.handle_wrapper(rule)(lambda e: func(e, handle)),
                state,
            )
            self.temp_handles.append(handle)
            return handle.func

        return decorator

    def set_temp_handles(self, temp_handles: list[TempHandle]):
        self.temp_handles = temp_handles
