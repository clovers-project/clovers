import time
import asyncio
import re
from typing import Any, Callable, Coroutine, Iterable, Sequence
from .typing import Method, MethodLib, Task
from .logger import logger


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
        self.startup_tasklist: list[Task] = []
        """启动任务列表"""
        self.shutdown_tasklist: list[Task] = []
        """关闭任务列表"""
        self.build_event: Callable[[Event], Any] | None = build_event
        """构建event"""
        self.build_result: Callable[[Any], Result] | None = build_result
        """构建result"""
        self.temp_handles_dict: dict[str, tuple[float, Handle]] = {}
        """临时任务列表"""
        self._handles: dict[int, Handle] = {}
        """已注册的响应器"""
        self._command_handle_keys: dict[str, list[tuple[int, int]]] = {}
        """指令触发的响应键列表"""
        self._regex_handle_keys: dict[re.Pattern, list[tuple[int, int]]] = {}
        """正则触发的响应键列表"""
        self._handles_queue: list[tuple[str, str | re.Pattern, int]] = []
        """已注册指令响应器队列"""
        self._key_handle_keys: dict[Any, list[tuple[int, int]]] = {}
        """键触发的响应器队列"""
        self._key_handles_dict: dict[Any, list[int]] = {}
        """键触发的响应器列表"""
        self._ready: bool = False

    def __str__(self) -> str:
        handle_queue = []
        handle_queue.extend(("command", command, key, priority) for command, x in self._command_handle_keys.items() for key, priority in x)
        handle_queue.extend(("regex", regex, key, priority) for regex, x in self._regex_handle_keys.items() for key, priority in x)
        handle_queue.extend(("key", keyword, key, priority) for keyword, x in self._key_handle_keys.items() for key, priority in x)
        handle_queue.sort(key=lambda x: x[2])
        info = []
        info.append(f"<Plugin {self.name}>")
        info.extend(
            f'\t<Handle key="{key}" priority="{priority}" check_type="{check_type}" command="{command}" />'
            for check_type, command, key, priority in handle_queue
        )
        info.append(f"</Plugin>")
        return "\n".join(info)

    def ready(self):
        """准备插件"""
        if not self._handles:
            return False
        if self._ready:
            return True
        handle_queue = []
        handle_queue.extend(("command", command, key, priority) for command, x in self._command_handle_keys.items() for key, priority in x)
        handle_queue.extend(("regex", regex, key, priority) for regex, x in self._regex_handle_keys.items() for key, priority in x)
        handle_queue.sort(key=lambda x: x[3])
        self._handles_queue = [(check_type, command, key) for check_type, command, key, _ in handle_queue]
        self._key_handles_dict = {key: [i for i, _ in sorted(queue, key=lambda x: x[1])] for key, queue in self._key_handle_keys.items()}
        self._ready = True
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
                raise TypeError(f"Checker: {checker} has an invalid type: {type(checker)}")

        def check(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
            if len(self.checker) == 1:
                checker = self.checker[0]
            else:
                checker = lambda event: all(checker(event) for checker in self.checker)

            async def wrapper(event):
                return await func(event) if checker(event) else None

            return wrapper

    type Ruleable = list[Callable[..., bool]] | Callable[..., bool] | Rule | None

    def handle_warpper(self, rule: Ruleable = None):
        """构建插件的原始event->result响应"""

        def decorator(func: Callable[..., Coroutine]):
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
            raise TypeError(f"Command: {commands} has an invalid type: {type(commands)}")

    def handle(
        self,
        commands: PluginCommands,
        properties: Iterable[str] = [],
        rule: Ruleable = None,
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
            handle_key = len(self._handles)
            self.commands_register(commands, handle_key, priority)
            handle = Handle(properties, block)
            handle.func = self.handle_warpper(rule)(func)
            self._handles[handle_key] = handle
            return handle.func

        return decorator

    def key_handle(
        self,
        key,
        properties: Iterable[str] = [],
        rule: Ruleable = None,
        priority: int = 0,
        block: bool = False,
    ):
        """
        创建键触发响应器
            key: 触发键
            properties: 额外参数
            rule: 响应规则
            priority: 优先级
            block: 是否阻断后续响应器
        """

        def decorator(func: Callable[..., Coroutine]):
            handle_key = len(self._handles)
            self._key_handle_keys.setdefault(key, []).append((handle_key, priority))
            handle = Handle(properties, block)
            handle.func = self.handle_warpper(rule)(func)
            self._handles[handle_key] = handle
            return handle.func

        return decorator

    def temp_handle(
        self,
        key: str,
        properties: Iterable[str] = [],
        timeout: float | int = 30.0,
        rule: Ruleable = None,
        block: bool = True,
    ):
        """
        创建插件临时指令响应器
            key: 临时指令的key
            properties: 额外参数
            timeout: 临时指令的过期时间
            rule: 响应规则
            block: 是否阻断后续响应器
        """

        def decorator(func: Callable[..., Coroutine]):
            handle = Handle(properties, block)
            middle_func = lambda e: func(e, self.Finish(self.temp_handles_dict, key))
            handle.func = self.handle_warpper(rule)(middle_func)
            self.temp_handles_dict[key] = time.time() + timeout, handle
            return handle.func

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

    def startup(self, func: Task):
        """注册一个启动任务"""
        self.startup_tasklist.append(func)

        return func

    def shutdown(self, func: Task):
        """注册一个结束任务"""
        self.shutdown_tasklist.append(func)

        return func

    def temp_check(self) -> bool:
        """检查是否有临时指令响应器"""
        if not self.temp_handles_dict:
            return False
        now = time.time()
        self.temp_handles_dict = {k: v for k, v in self.temp_handles_dict.items() if v[0] > now}
        if not self.temp_handles_dict:
            return False
        return True

    def key_match(self, key) -> list[tuple[Handle, Event]] | None:
        if key not in self._key_handles_dict:
            return
        index_lst = self._key_handles_dict[key]
        event = Event("", [])
        return [(self._handles[i], event) for i in index_lst]

    def command_match(self, message: str) -> list[tuple[Handle, Event]] | None:
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


def kwfilter(func: Method) -> Method:

    co_argcount = func.__code__.co_argcount
    if co_argcount == 0:
        return lambda *args, **kwargs: func()
    kw = set(func.__code__.co_varnames[:co_argcount])

    async def wrapper(*args, **kwargs):
        return await func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    return wrapper


class Adapter:
    def __init__(self, name: str = "") -> None:
        self.name: str = name
        self.properties_lib: MethodLib = {}
        self.sends_lib: MethodLib = {}
        self.calls_lib: MethodLib = {}

    def property_method(self, method_name: str) -> Callable:
        """添加一个获取参数方法"""

        def decorator(func: Method):
            method = kwfilter(func)
            if method_name not in self.calls_lib:
                self.calls_lib[method_name] = method
            self.properties_lib[method_name] = method
            return func

        return decorator

    def send_method(self, method_name: str) -> Callable:
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

    async def response(self, handle: Handle, event: Event, extra):
        try:
            if handle.properties:
                coros = []
                keys = []
                for key in handle.properties:
                    if key in event.properties:
                        continue
                    coros.append(self.properties_lib[key](**extra))
                    keys.append(key)
                event.properties.update({k: v for k, v in zip(keys, await asyncio.gather(*coros))})
            event.calls = self.calls_lib
            event.extra = extra
            result = await handle(event)
            if not result:
                return
            await self.sends_lib[result.send_method](result.data, **extra)
            return handle.block
        except:
            logger.exception("response")
