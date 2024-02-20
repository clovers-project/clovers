import sys

sys.path.append(r"D:\GIT\clovers_core")
from io import BytesIO
from collections.abc import Coroutine
from clovers_core.adapter import AdapterMethod
from clovers_core.plugin import Result
from nonebot.matcher import Matcher
from nonebot.adapters.qq import MessageEvent, Message, MessageSegment


def initializer(main: type[Matcher]) -> AdapterMethod:
    method = AdapterMethod()

    @method.send("text")
    async def _(message: str):
        """发送纯文本"""
        await main.send(message)

    @method.send("image_url")
    async def _(message: str, main: type[Matcher]):
        """发送图片"""
        await main.send(MessageSegment.image(message))

    @method.send("image")
    async def _(message: BytesIO, main: type[Matcher]):
        """发送图片"""
        await main.send(MessageSegment.file_image(message))

    @method.send("list")
    async def _(message: list[Result], main: type[Matcher]):
        """发送图片文本混合信息"""
        msg = Message()
        for seg in message:
            if seg.send_method == "text":
                msg += seg.data
            elif seg.send_method == "image":
                msg += MessageSegment.image(seg.data)
        await main.send(msg)

    @method.send("segmented")
    async def _(message: Coroutine):
        """发送分段信息"""
        async for seg in message():
            await method.send[seg.send_method](seg.data)

    @method.kwarg("user_id")
    async def _(event: MessageEvent):
        return event.get_user_id()

    @method.kwarg("group_id")
    async def _(event: MessageEvent):
        return getattr(event, "group_id", getattr(event, "guild_id", None))

    return method
