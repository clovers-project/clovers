from nonebot import get_driver
from clovers.core.plugin import Plugin
from clovers.core.adapter import Adapter

# 加载配置
driver = get_driver()
global_config = driver.config

command_start = {x for x in global_config.command_start if x}


def extract_command(msg: str):
    for command in command_start:
        if msg.startswith(command):
            return msg[len(command) :]
    return msg


Bot_NICKNAME = list(global_config.nickname)
Bot_NICKNAME = Bot_NICKNAME[0] if Bot_NICKNAME else "bot"


def new_adapter(plugins: list[Plugin] | None = None):
    """创建新的adapter，包括注入插件和全局方法"""
    adapter = Adapter()
    if plugins:
        adapter.plugins = plugins

    @adapter.method.kwarg("Bot_Nickname")
    async def _():
        return Bot_NICKNAME

    return adapter
