import sys

sys.path.append(r"D:\GIT\clovers_core")
sys.path.append(r"D:\GIT\clovers_leafgame")

import nonebot
from nonebot import on_message, get_driver
from nonebot.matcher import Matcher


from nonebot.adapters.qq import Bot as QQBot, MessageEvent as QQMsgEvent
from nonebot.adapters.onebot.v11 import Bot as v11Bot, MessageEvent as v11MsgEvent
from .adapters import qq, v11
from .clovers import adapter

driver = get_driver()

driver.on_startup(adapter.task)

Bot_NICKNAME = list(nonebot.get_driver().config.nickname)
Bot_NICKNAME = Bot_NICKNAME[0] if Bot_NICKNAME else "bot"

command_start = {x for x in driver.config.command_start if x}


def extract_command(msg: str):
    for command in command_start:
        if msg.startswith(command):
            return msg[len(command) :]
    return msg


@adapter.main_method.kwarg("Bot_Nickname")
async def _():
    return Bot_NICKNAME


main = on_message(priority=50, block=True)


adapter.methods["QQ"] = qq.initializer(main)


@main.handle()
async def _(matcher: Matcher, bot: QQBot, event: QQMsgEvent):
    command = extract_command(event.get_plaintext())
    if await adapter.response("QQ", command, bot=bot, event=event):
        matcher.stop_propagation()


adapter.methods["v11"] = v11.initializer(main)


@main.handle()
async def _(matcher: Matcher, bot: v11Bot, event: v11MsgEvent):
    command = extract_command(event.get_plaintext())
    if await adapter.response("v11", command, bot=bot, event=event):
        matcher.stop_propagation()
