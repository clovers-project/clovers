from typing import Protocol, Literal, Any, overload
from collections.abc import Sequence, Coroutine
from clovers import Adapter, Plugin, EventType
from clovers.base import Coro


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
    async def send(self, key: Literal["text"], msg: str): ...
    @overload
    async def send(self, key: Literal["image"], msg: str): ...
    @overload
    async def call(self, key: Literal["member_info"], user_id: str) -> UserInfo: ...
    @overload
    def call(self, key: Literal["member_list"], user_id: str) -> Coroutine[Any, Any, Sequence[UserInfo]] | None: ...
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
