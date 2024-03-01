import sys

sys.path.append(r"D:\GIT\clovers_core")
sys.path.append(r"D:\GIT\clovers_leafgame")
import os
from pathlib import Path
from pydantic import BaseModel
from nonebot import on_message, get_driver
from nonebot.matcher import Matcher
from clovers_core.plugin import PluginLoader
from clovers_core.adapter import Adapter
from nonebot.adapters.qq import Bot as QQBot, MessageEvent as QQMsgEvent
from nonebot.adapters.onebot.v11 import Bot as v11Bot, MessageEvent as v11MsgEvent
from .adapters import qq, v11

# 加载配置
driver = get_driver()


global_config = driver.config

clovers_config_file = getattr(global_config, "clovers_config_file", "clovers.toml")
os.environ["clovers_config_file"] = clovers_config_file

# 添加环境变量之后加载config
from clovers_core.config import config as clovers_config


# 加载clovers配置
class Config(BaseModel):
    plugins_path: str = "./clovers/plugins"
    plugins_list: list = []


config_key = __package__
config = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config.dict()

plugins_path = Path(config.plugins_path)
plugins_path.mkdir(exist_ok=True, parents=True)
loader = PluginLoader(plugins_path, config.plugins_list)
adapter = Adapter()
adapter.plugins = loader.plugins

driver.on_startup(adapter.startup)

Bot_NICKNAME = list(global_config.nickname)
Bot_NICKNAME = Bot_NICKNAME[0] if Bot_NICKNAME else "bot"

command_start = {x for x in global_config.command_start if x}


def extract_command(msg: str):
    for command in command_start:
        if msg.startswith(command):
            return msg[len(command) :]
    return msg


@adapter.method.kwarg("Bot_Nickname")
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
