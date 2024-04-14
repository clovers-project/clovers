import os
from pathlib import Path
from pydantic import BaseModel
from nonebot import get_driver
from clovers.core.plugin import PluginLoader
from .adapters.main import extract_command, new_adapter

# 加载配置
driver = get_driver()
global_config = driver.config
clovers_config_file = getattr(global_config, "clovers_config_file", "clovers.toml")
os.environ["clovers_config_file"] = clovers_config_file

# 添加环境变量之后加载config
from clovers.core.config import config as clovers_config


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
adapter = new_adapter(loader.plugins)

driver.on_startup(adapter.startup)


from nonebot import on_message
from nonebot.matcher import Matcher

main = on_message(priority=50, block=True)

from .adapters import qq
from nonebot.adapters.qq import Bot as QQBot, MessageEvent as QQMsgEvent

adapter.methods["QQ"] = qq.initializer(main)


@main.handle()
async def _(matcher: Matcher, bot: QQBot, event: QQMsgEvent):
    command = extract_command(event.get_plaintext())
    if await adapter.response("QQ", command, bot=bot, event=event):
        matcher.stop_propagation()


from .adapters import v11
from nonebot.adapters.onebot.v11 import Bot as v11Bot, MessageEvent as v11MsgEvent

adapter.methods["v11"] = v11.initializer(main)


@main.handle()
async def _(matcher: Matcher, bot: v11Bot, event: v11MsgEvent):
    command = extract_command(event.get_plaintext())
    if await adapter.response("v11", command, bot=bot, event=event):
        matcher.stop_propagation()
