import sys

sys.path.append(r"D:\GIT\clovers_core")
from io import BytesIO
from collections.abc import Callable, Coroutine, AsyncGenerator
from clovers.core.adapter import AdapterMethod
from clovers.core.plugin import Result
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageEvent,
    GroupMessageEvent,
    Message,
    MessageSegment,
    GROUP_ADMIN,
    GROUP_OWNER,
)


def initializer(main: type[Matcher]) -> AdapterMethod:
    method = AdapterMethod()

    @method.send("text")
    async def _(message: str, send: Callable[..., Coroutine] = main.send):
        """发送纯文本"""
        await send(message)

    @method.send("image")
    async def _(message: BytesIO, send: Callable[..., Coroutine] = main.send):
        """发送图片"""
        await send(MessageSegment.image(message))

    @method.send("list")
    async def _(message: list[Result], send: Callable[..., Coroutine] = main.send):
        """发送图片文本混合信息"""
        msg = Message()
        for seg in message:
            if seg.send_method == "text":
                msg += seg.data
            elif seg.send_method == "image":
                msg += MessageSegment.image(seg.data)
        await send(msg)

    @method.send("segmented")
    async def _(message: AsyncGenerator[Result, None], send: Callable[..., Coroutine] = main.send):
        """发送分段信息"""
        async for seg in message:
            await method.send_dict[seg.send_method](seg.data, send)

    @method.kwarg("user_id")
    async def _(event: MessageEvent):
        return event.get_user_id()

    @method.kwarg("group_id")
    async def _(event: MessageEvent):
        group_id = getattr(event, "group_id", None)
        return str(group_id) if group_id else None

    @method.kwarg("to_me")
    async def _(event: MessageEvent):
        return event.to_me

    @method.kwarg("nickname")
    async def _(event: MessageEvent):
        return event.sender.card or event.sender.nickname

    @method.kwarg("avatar")
    async def _(event: MessageEvent) -> str:
        return f"https://q1.qlogo.cn/g?b=qq&nk={event.user_id}&s=640"

    @method.kwarg("group_avatar")
    async def _(event: MessageEvent) -> str:
        if isinstance(event, GroupMessageEvent):
            return f"https://p.qlogo.cn/gh/{event.group_id}/{event.group_id}/640"
        return ""

    @method.kwarg("image_list")
    async def _(event: MessageEvent):
        url = [msg.data["url"] for msg in event.message if msg.type == "image"]
        if event.reply:
            url += [msg.data["url"] for msg in event.reply.message if msg.type == "image"]
        return url

    @method.kwarg("permission")
    async def _(bot: Bot, event: MessageEvent) -> int:
        if await SUPERUSER(bot, event):
            return 3
        if await GROUP_OWNER(bot, event):
            return 2
        if await GROUP_ADMIN(bot, event):
            return 1
        return 0

    @method.kwarg("at")
    async def _(event: MessageEvent) -> list[str]:
        return [str(msg.data["qq"]) for msg in event.message if msg.type == "at"]

    @method.kwarg("send_group_message")
    async def _(bot: Bot) -> Callable[[int, Result], Coroutine]:
        async def send_group_message(group_id: int, result: Result):
            send = lambda message: bot.send_group_msg(group_id=group_id, message=message)
            await method.send_dict[result.send_method](result.data, send)

        return send_group_message

    return method
