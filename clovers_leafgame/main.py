from io import BytesIO
from collections.abc import AsyncGenerator
from clovers.core.plugin import Plugin, Result
from clovers.core.config import config as clovers_config
from clovers_leafgame.core.clovers import Event
from .manager import Manager
from .config import Config

config_key = __package__
config_data = Config.parse_obj(clovers_config.get(config_key, {}))
"""主配置类"""
clovers_config[config_key] = config_data.dict()


def build_result(result):
    if isinstance(result, str):
        return Result("text", result)
    if isinstance(result, BytesIO):
        return Result("image", result)
    if isinstance(result, list):
        return Result("list", [build_result(seg) for seg in result])
    if isinstance(result, AsyncGenerator):

        async def output():
            async for x in result:
                yield build_result(x)

        return Result("segmented", output())
    return result


plugin = Plugin(build_event=lambda event: Event(event), build_result=build_result)
"""小游戏插件实例"""

manager = Manager(config_data.main_path)
"""小游戏管理器实例"""
