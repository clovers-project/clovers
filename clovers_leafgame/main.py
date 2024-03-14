from io import BytesIO
from clovers_core.plugin import Plugin, Result
from clovers_core.config import config as clovers_config
from clovers_leafgame.core.clovers import Event
from .manager import Manager
from .config import Config

config = Config.parse_obj(clovers_config.get(__package__, {}))
"""主配置类"""

plugin = Plugin(
    build_event=lambda event: Event(event),
    build_result=lambda result: (
        Result("text", result) if isinstance(result, str) else Result("image", result) if isinstance(result, BytesIO) else result
    ),
)
"""小游戏插件实例"""

manager = Manager(config.main_path)
"""小游戏管理器实例"""
