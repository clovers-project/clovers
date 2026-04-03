from collections.abc import Callable
import asyncio
from .utils import kwfilter, protocol_format, check_compatible, is_coro
from ..logger import logger
from ..base import Coro, AdapterCore, AdapterMethod, AdapterMethodLib, BaseHandle, Event


class MethodRegError(Exception): ...


class Adapter(AdapterCore):
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
        self.sends_lib: AdapterMethodLib = {}
        self.calls_lib: AdapterMethodLib = {}
        self.__protocol = {"send": {}, "call": {}}

    @property
    def info(self):
        return {
            "name": self.name,
            "sends_lib": list(self.sends_lib.keys()),
            "calls_lib": list(self.calls_lib.keys()),
            "properties_lib": list(self.calls_lib.keys()),
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

    def property_method(self, method_name: str):
        """添加一个获取参数方法"""

        def decorator(func: AdapterMethod):
            if method_name in self.calls_lib:
                raise MethodRegError(f"Method '{method_name}' already exists (from: {func.__module__}.{func.__qualname__})")
            if annot := func.__annotations__.get("return"):
                self.__protocol["call"][method_name] = annot
            self.calls_lib[method_name] = kwfilter(func)
            return func

        return decorator

    def send_method(self, method_name: str):
        """添加一个发送消息方法"""

        def decorator(func: AdapterMethod):
            if method_name in self.sends_lib:
                raise MethodRegError(f"Method '{method_name}' already exists (from: {func.__module__}.{func.__qualname__})")
            name = func.__code__.co_varnames[0]
            if annot := func.__annotations__.get(name):
                self.__protocol["send"][method_name] = annot
            self.sends_lib[method_name] = kwfilter(func)
            return func

        return decorator

    def call_method(self, method_name: str):
        """添加一个调用方法"""

        def decorator(func: AdapterMethod):
            if method_name in self.calls_lib:
                raise MethodRegError(f"Method '{method_name}' already exists (from: {func.__module__}.{func.__qualname__})")
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
            self.calls_lib[method_name] = kwfilter(func)
            return func

        return decorator

    def mixin(self, adapter: AdapterCore):
        """混合其他兼容方法"""
        for k, func in adapter.sends_lib.items():
            try:
                self.send_method(k)(func)
            except MethodRegError as e:
                logger.warning(e)
        for k, func in adapter.calls_lib.items():
            try:
                self.call_method(k)(func)
            except MethodRegError as e:
                logger.warning(e)

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
