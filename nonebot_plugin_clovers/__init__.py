import os
from pathlib import Path
from pydantic import BaseModel
from nonebot import get_driver
from clovers.core.adapter import AdapterMethod
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


def add_response(Bot, Event, adapter_method: AdapterMethod, adapter_key: str):
    adapter.methods[adapter_key] = adapter_method

    @main.handle()
    async def _(matcher: Matcher, bot: Bot, event: Event):
        command = extract_command(event.get_plaintext())
        if await adapter.response(adapter_key, command, bot=bot, event=event):
            matcher.stop_propagation()


from .adapters import qq
from nonebot.adapters.qq import Bot as QQBot, MessageEvent as QQMsgEvent

add_response(QQBot, QQMsgEvent, qq.initializer(main), "QQ")


from .adapters import v11
from nonebot.adapters.onebot.v11 import Bot as v11Bot, MessageEvent as v11MsgEvent

add_response(v11Bot, v11MsgEvent, v11.initializer(main), "v11")
