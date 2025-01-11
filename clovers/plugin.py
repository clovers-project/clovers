import time
import re
from collections.abc import Callable, Coroutine, Iterable, Sequence
from typing import Any
from .typing import MethodLib, Task


class Result:
    def __init__(self, send_method: str, data) -> None:
        self.send_method = send_method
        self.data = data


class Event:
    def __init__(
        self,
        raw_command: str,
        args: Sequence[str],
    ):
        self.raw_command = raw_command
        self.args = args
        self.properties: dict = {}
        self.calls: MethodLib = {}
        self.extra: dict = {}

    async def call(self, key, *args):
        """调用适配器方法，只接受位置参数"""
        return await self.calls[key](*args, **self.extra)


class Handle:
    func: Callable[[Event], Coroutine[None, None, Result | None]]

    def __init__(self, properties: Iterable[str], block: bool):
        self.properties = properties
        self.block = block

    async def __call__(self, event: Event):
        return await self.func(event)


type PluginCommands = str | Iterable[str] | re.Pattern | None


class Plugin:

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
        self.temp_handles: dict[str, tuple[float, Handle]] = {}
        """临时任务列表"""
        self.startup_tasklist: list[Task] = []
        """启动任务列表"""
        self.shutdown_tasklist: list[Task] = []
        """关闭任务列表"""
        self.build_event: Callable[[Event], Any] | None = build_event
        """构建event"""
        self.build_result: Callable[[Any], Result] | None = build_result
        """构建result"""
        self._handles: dict[int, Handle] = {}
        """已注册的响应器"""
        self._handles_queue: list[tuple[str, str | re.Pattern, int]] = []
        """已注册指令响应器队列"""
        self._command_handle_keys: dict[str, list[tuple[int, int]]] = {}
        """指令触发的响应键列表"""
        self._regex_handle_keys: dict[re.Pattern, list[tuple[int, int]]] = {}
        """正则触发的响应键列表"""

    def ready(self):
        """准备插件"""
        if not self._handles:
            return False
        handle_queue = []
        handle_queue.extend(
            [("command", command, key, priority) for command, x in self._command_handle_keys.items() for key, priority in x]
        )
        handle_queue.extend([("regex", regex, key, priority) for regex, x in self._regex_handle_keys.items() for key, priority in x])
        handle_queue.sort(key=lambda x: x[3])
        self._handles_queue = [(check_type, command, key) for check_type, command, key, _ in handle_queue]
        return True

    @property
    def handles(self):
        """获取已注册的响应器"""
        return (handle for handle in self._handles.values())

    class Rule:
        checker: list[Callable[..., bool]]

        def __init__(self, checker: list[Callable[..., bool]] | Callable[..., bool]):
            if isinstance(checker, list):
                self.checker = checker
            elif callable(checker):
                self.checker = [checker]
            else:
                raise TypeError(f"checker：{checker} 类型错误：{type(checker)}")

        def check(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
            if len(self.checker) == 1:
                checker = self.checker[0]
            else:
                checker = lambda event: all(checker(event) for checker in self.checker)

            async def wrapper(event):
                if checker(event):
                    return await func(event)

            return wrapper

    def handle_warpper(self, func: Callable[..., Coroutine]):
        """构建插件的原始event->result响应"""
        if build_event := self.build_event:
            middle_func = lambda e: func(build_event(e))
        else:
            middle_func = func

        if build_result := self.build_result:

            async def wrapper(event):
                if result := await middle_func(event):
                    return build_result(result)

            return wrapper
        else:
            return middle_func

    def commands_register(self, commands: PluginCommands, key: int, priority: int):
        """
        指令注册器
            commands: 指令
            key: 响应器的key
            priority: 优先级
        """
        data = (key, priority)
        if not commands:
            self._command_handle_keys.setdefault("", []).append(data)
        elif isinstance(commands, str):
            self._regex_handle_keys.setdefault(re.compile(commands), []).append(data)
        elif isinstance(commands, re.Pattern):
            self._regex_handle_keys.setdefault(commands, []).append(data)
        elif isinstance(commands, Iterable):
            for command in commands:
                self._command_handle_keys.setdefault(command, []).append(data)
        else:
            raise TypeError(f"指令：{commands} 类型错误：{type(commands)}")

    def handle(
        self,
        commands: PluginCommands,
        properties: Iterable[str] = [],
        rule: list[Callable[..., bool]] | Callable[..., bool] | Rule | None = None,
        priority: int = 0,
        block: bool = True,
    ):
        """
        注册插件指令响应器
            commands: 指令
            properties: 额外参数
            rule: 响应规则
            priority: 优先级
            block: 是否阻断后续响应器
        """

        def decorator(func: Callable[..., Coroutine]):
            key = len(self._handles)
            self.commands_register(commands, key, priority)
            handle = Handle(properties, block)
            if rule:
                if isinstance(rule, self.Rule):
                    func = rule.check(func)
                else:
                    func = self.Rule(rule).check(func)
            handle.func = self.handle_warpper(func)
            self._handles[key] = handle

        return decorator

    def temp_handle(
        self,
        key: str,
        properties: Iterable[str] = [],
        timeout: float | int = 30.0,
        rule: list[Callable[..., bool]] | Callable[..., bool] | Rule | None = None,
        block: bool = True,
    ):
        """
        创建插件临时指令响应器
            key: 临时指令的key
            properties: 额外参数
            timeout: 临时指令的过期时间
            block: 是否阻断后续响应器
        """

        def decorator(func: Callable[..., Coroutine]):
            handle = Handle(properties, block)
            middle_func = lambda e: func(e, self.Finish(self.temp_handles, key))
            if rule:
                if isinstance(rule, self.Rule):
                    middle_func = rule.check(middle_func)
                else:
                    middle_func = self.Rule(rule).check(middle_func)
            handle.func = self.handle_warpper(middle_func)
            self.temp_handles[key] = time.time() + timeout, handle

        return decorator

    class Finish:
        def __init__(
            self,
            temp_handles: dict[str, tuple[float, Handle]],
            key: str,
        ) -> None:
            self.handles = temp_handles
            self.key = key

        def __call__(self):
            """结束临时指令响应器"""
            del self.handles[self.key]

        def delay(self, timeout: float | int = 30.0):
            """延迟临时指令响应器的过期时间"""
            self.handles[self.key] = (time.time() + timeout, self.handles[self.key][1])

    def startup(self, func: Callable[[], Coroutine]):
        """注册一个启动任务"""
        self.startup_tasklist.append(func)

        return func

    def shutdown(self, func: Callable[[], Coroutine]):
        """注册一个结束任务"""
        self.shutdown_tasklist.append(func)

        return func

    def temp_check(self) -> bool:
        """检查是否有临时指令响应器"""
        if not self.temp_handles:
            return False
        now = time.time()
        self.temp_handles = {k: v for k, v in self.temp_handles.items() if v[0] > now}
        if not self.temp_handles:
            return False
        return True

    def __call__(self, message: str) -> list[tuple[Handle, Event]] | None:
        command_list = message.split()
        if not command_list:
            return
        command_start = command_list[0]
        data = []
        for check_type, command, key in self._handles_queue:
            match check_type:
                case "command":
                    assert isinstance(command, str)
                    if not command_start.startswith(command):
                        continue
                    if command_start == command:
                        args = command_list[1:]
                    else:
                        command_list[0] = command_list[0][len(command) :]
                        args = command_list
                    event = Event(message, args)
                    data.append((self._handles[key], event))
                case "regex":
                    assert isinstance(command, re.Pattern)
                    if args := re.match(command, message):
                        event = Event(message, args.groups())
                        data.append((self._handles[key], event))
                case _:
                    assert False, f"check_type {check_type} are not supported"
        return data
