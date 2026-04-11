from functools import wraps
from abc import ABC, abstractmethod
from typing import Any, Protocol
from collections.abc import Callable, Coroutine, Iterable, Sequence

type Coro[T] = Coroutine[Any, Any, T]
type AdapterMethod[T] = Callable[..., Coro[T]]
type AdapterMethodLib[T] = dict[str, AdapterMethod[T]]
type Task = Callable[[], Coro[None] | None]
type EventHandler = Callable[[Event], Coro[Result | None]]


def kwfilter(func: AdapterMethod) -> AdapterMethod:
    """方法参数过滤器"""

    if func.__code__.co_flags & 0x0C:
        return func
    co_argcount = func.__code__.co_argcount
    if co_argcount == 0:
        return wraps(func)(lambda *args, **kwargs: func())
    kw = set(func.__code__.co_varnames[:co_argcount])

    @wraps(func)
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

    def __init__(self, name: str = "") -> None:
        self.name: str = name
        """初始化方式"""
        self.sends_lib = {}
        """发送方法库"""
        self.calls_lib = {}
        """调用方法库"""

    @property
    def info(self):
        return {
            "name": self.name,
            "sends_lib": list(self.sends_lib.keys()),
            "calls_lib": list(self.calls_lib.keys()),
        }

    def register_call[T: AdapterMethod](self, method_name: str, func: T) -> T:
        self.calls_lib[method_name] = kwfilter(func)
        return func

    def register_send[T: AdapterMethod[None]](self, method_name: str, func: T) -> T:
        self.sends_lib[method_name] = kwfilter(func)
        return func

    def property_method(self, method_name: str):
        """添加一个获取参数方法

        Args:
            method_name (str): 方法名
        Returns:
            (AdapterMethod) -> AdapterMethod: 属性方法装饰器
        """
        return lambda func: self.register_call(method_name, func)

    def send_method(self, method_name: str):
        """添加一个发送消息方法

        Args:
            method_name (str): 方法名
        Returns:
            (AdapterMethod) -> AdapterMethod: 发送方法装饰器
        """
        return lambda func: self.register_send(method_name, func)

    def call_method(self, method_name: str):
        """添加一个调用方法

        Args:
            method_name (str): 方法名
        Returns:
            (AdapterMethod) -> AdapterMethod: 调用方法装饰器
        """
        return lambda func: self.register_call(method_name, func)

    def mixin(self, adapter: "Adapter"):
        """混合其他兼容方法

        Args:
            adapter (Adapter): 其他适配器实例
        """
        for k, func in adapter.sends_lib.items():
            self.register_send(k, func)
        for k, func in adapter.calls_lib.items():
            self.register_call(k, func)


class EventType(Protocol):
    """基础事件协议类型，本类型仅用作描述 Event

    Attributes:
        message (str): 触发消息
        args (Sequence[str]): 指令参数
        properties (dict[str, Any]): 需要的额外属性，由插件声明
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
    """

    message: str
    args: Sequence[str]
    properties: dict

    def __init__(self, message: str, args: Sequence[str], properties: dict[str, Any], adapter: Adapter, extra: dict):
        self.message = message
        self.args = args
        self.properties = properties
        self._adapter = adapter
        self._extra = extra

    @property
    def info(self) -> dict:
        return {"message": self.message, "args": self.args, "properties": self.properties}

    def send(self, key: str, message: Any):
        """执行适配器发送方法

        Args:
            key (str): 适配器方法名
            message (Any): 适配器方法参数

        Returns:
            Coro[None] | None: 适配器发送方法的 Coro，如 key 不存在则返回 None
        """
        if key not in self._adapter.sends_lib:
            return
        return self._adapter.sends_lib[key](message, **self._extra)

    def call(self, key: str, *args):
        """执行适配器调用方法，只接受位置参数

        Args:
            key (str): 适配器方法名
            *args: 适配器方法参数

        Returns:
            Coro[Any] | None: 适配器调用方法的 Coro，如 key 不存在则返回 None
        """
        if key not in self._adapter.calls_lib:
            return
        return self._adapter.calls_lib[key](*args, **self._extra)

    def __getattr__(self, name: str):
        try:
            return self.properties[name]
        except KeyError:
            raise AttributeError(f"Event object has no attribute '{name}'")


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

    async def send(self, event: EventType):
        if (coro := event.send(self.key, self.data)) is None:
            return
        await coro


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
