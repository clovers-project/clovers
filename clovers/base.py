from abc import ABC, abstractmethod
from typing import Any, Protocol
from collections.abc import Callable, Coroutine, Iterable, Sequence


type Coro[T] = Coroutine[Any, Any, T]
type AdapterMethod[T] = Callable[..., Coro[T]]
type AdapterMethodLib[T] = dict[str, AdapterMethod[T]]
type Task = Callable[[], Coro[None]] | Callable[[], None]
type EventHandler = Callable[[Event], Coro[Result | None]]


def kwfilter(func: AdapterMethod) -> AdapterMethod:
    """方法参数过滤器"""
    if func.__code__.co_flags & 0x0C:
        return func
    co_argcount = func.__code__.co_argcount
    if co_argcount == 0:
        return lambda *args, **kwargs: func()
    kw = set(func.__code__.co_varnames[:co_argcount])

    def wrapper(*args, **kwargs):
        return func(*args, **{k: v for k, v in kwargs.items() if k in kw})

    return wrapper


class Info(ABC):

    @property
    @abstractmethod
    def info(self) -> dict[str, Any]:
        """信息"""
        raise NotImplementedError

    def __repr__(self) -> str:
        return repr({self.__class__.__name__: self.info})


class Adapter(Info):
    """适配器类

    Attributes:
        sends_lib (AdapterMethodLib): 发送方法
        calls_lib (AdapterMethodLib): 调用方法
    """

    sends_lib: AdapterMethodLib[None]
    calls_lib: AdapterMethodLib[Any]

    def call_decorator(self, method_name: str, func: AdapterMethod):
        self.calls_lib[method_name] = kwfilter(func)
        return func

    def send_decorator(self, method_name: str, func: AdapterMethod):
        self.sends_lib[method_name] = kwfilter(func)
        return func

    def property_method(self, method_name: str) -> Callable[[AdapterMethod], AdapterMethod]:
        """添加一个获取参数方法"""
        return lambda func: self.call_decorator(method_name, func)

    def send_method(self, method_name: str) -> Callable[[AdapterMethod], AdapterMethod]:
        """添加一个发送消息方法"""
        return lambda func: self.send_decorator(method_name, func)

    def call_method(self, method_name: str) -> Callable[[AdapterMethod], AdapterMethod]:
        """添加一个调用方法"""
        return lambda func: self.call_decorator(method_name, func)

    def mixin(self, adapter: "Adapter"):
        """混合其他兼容方法"""
        for k, func in adapter.sends_lib.items():
            self.send_decorator(k, func)
        for k, func in adapter.calls_lib.items():
            self.call_decorator(k, func)


class Result[K: str, T](Info):
    """插件响应结果

    Attributes:
        key (str): 响应方法
        data (Any): 响应数据
    """

    key: K
    data: T

    def __init__(self, key: K, data: T) -> None:
        self.key = key
        self.data = data

    @property
    def info(self):
        return {"key": self.key, "data": self.data}


class EventType(Protocol):
    """基础事件协议类型，本类型仅用作描述 Event

    Attributes:
        message (str): 触发消息
        args (Sequence[str]): 指令参数
        properties (dict[str, Any]): 需要的额外属性，由插件声明

    Methods:
        send (key: str, message: Any): 执行适配器发送方法
        call (key: str, *args): 执行适配器调用方法并获取返回值
    """

    message: str
    args: Sequence[str]
    properties: dict
    ...

    def send(self, key: str, message: Any) -> Coro[None] | None: ...

    def call(self, key: str, *args) -> Coro[Any] | None: ...


class Event(Info):
    """触发响应的事件

    Attributes:
        message (str): 触发插件的消息原文
        args (Sequence[str]): 指令参数
        properties (dict[str, Any]): 需要的额外属性，由插件声明

    Methods:
        send (key: str, message: Any): 执行适配器发送方法
        call (key: str, *args): 执行适配器调用方法并获取返回值
    """

    message: str
    args: Sequence[str]
    properties: dict

    def __init__(self, message: str, args: Sequence[str], properties: dict[str, Any], adapter: Adapter, extra: dict):
        self.message = message
        self.args = args
        self.properties = properties
        self.__adapter = adapter
        self.__extra = extra

    @property
    def info(self) -> dict:
        return {"message": self.message, "args": self.args, "properties": self.properties}

    def send(self, key: str, message: Any):
        """执行适配器发送方法"""
        if key not in self.__adapter.sends_lib:
            return
        return self.__adapter.sends_lib[key](message, **self.__extra)

    def call(self, key: str, *args):
        """执行适配器调用方法，只接受位置参数"""
        if key not in self.__adapter.calls_lib:
            return
        return self.__adapter.calls_lib[key](key, *args, **self.__extra)

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
