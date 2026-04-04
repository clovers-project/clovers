from typing import Protocol, Literal, Any, overload, Optional, Any
from clovers import Adapter, Plugin, EventType
from collections.abc import Sequence, Callable, Coroutine, Iterable, Generator
from clovers.adapter.utils import check_compatible

type Coro[T] = Coroutine[Any, Any, T]
type AsyncFunc[*Arg, T] = Callable[[*Arg], Coro[T]]


class UserInfo:
    user_id: str
    avatar: str
    nickname: str


class UserInfo2:
    user_id: str
    avatar: str
    nickname: str


adapter = Adapter("Test")
plugin = Plugin("test")


class Event(EventType, Protocol):
    user_id: str
    group_id: str

    @overload
    async def send(self, key: Literal["text"], msg: str | bytes): ...
    @overload
    async def send(self, key: Literal["image"], msg: str | bytes): ...
    @overload
    async def call(self, key: Literal["member_info"], user_id: str) -> UserInfo: ...
    @overload
    def call(self, key: Literal["member_list"], user_id: str) -> Coro[Sequence[UserInfo]] | None: ...
    def send(self, key: str, *args, **kwargs):
        raise NotImplementedError

    def call(self, key: str, *args, **kwargs):
        raise NotImplementedError


@adapter.property_method("user_id")
async def _(recv: dict, clienr: Any) -> str: ...
@adapter.property_method("group_id")
async def _(recv: dict, clienr: Any) -> str: ...
@adapter.send_method("text")
async def _(message: str, recv: dict, clienr: Any): ...
@adapter.send_method("image")
async def _(message: str, recv: dict, clienr: Any): ...
@adapter.call_method("member_info")
async def _(user_id: str, /, recv: dict, clienr: Any) -> UserInfo2: ...
@adapter.call_method("member_list")
async def _(user_id: str | int, /, recv: dict, clienr: Any) -> list[UserInfo2]: ...


plugin.protocol = Event
print(adapter.check_protocol(plugin.protocol))

# 判断 TypeA 的范围是否小于 TypeB 的范围
print(1, check_compatible(int, str | int))

type string = str | bytearray | bytes

print(2, check_compatible(Literal["str"], string))

print(3, check_compatible(str | bytes, str | bytes | None))

print(4, check_compatible(list[str | bytes], list[Optional[str | bytes]]))

print(5, check_compatible(list[Optional[str | bytes]], Sequence[str | bytes | None]))

print()


# 范围更小的函数被定义为，接受范围更大的参数返回范围更小的值
print(
    6.0,
    check_compatible(Callable[[Iterable[int | None]], Coroutine[Any, Any, list[int]]], AsyncFunc[[Generator[int]], Iterable[int | None]]),
)
print(
    6.1,
    check_compatible(Callable[[Generator[int | None]], Coroutine[Any, Any, list[int]]], AsyncFunc[[Iterable[int]], Iterable[int | None]]),
)
print(
    6.2,
    check_compatible(Callable[[Iterable[int | None]], Coroutine[Any, Any, Iterable[int]]], AsyncFunc[[Iterable[int]], list[int | None]]),
)

print()


class MyClassA:
    val: int


class MySubClassA(MyClassA):
    val: str


class MyClassB:
    val: int | str


class MySubClassB(MyClassB): ...


# 子类被定义为范围更小，即使字段被重新定义

print(7.1, check_compatible(MySubClassA, MyClassA))
print(7.2, check_compatible(MyClassA, MySubClassA))

# 无关系的两个类仅看类内定义的字段范围

print(8.1, check_compatible(MyClassA, MyClassB))
print(8.2, check_compatible(MySubClassA, MyClassB))


class MyClassC:
    val: bytes


print(8.3, check_compatible(MyClassC, MyClassB))

print()

# 递归判断


class EventA:
    val1: int
    val2: list[MyClassA]


class EventB:
    val1: int | str
    val2: Sequence[MyClassB | MyClassC]


print(9.1, check_compatible(AsyncFunc[..., EventA], AsyncFunc[..., EventB]))
print(9.2, check_compatible(AsyncFunc[..., EventB], AsyncFunc[..., EventA]))
