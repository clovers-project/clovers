"""小游戏运行实例"""

from io import BytesIO
from clovers_core.plugin import Plugin, Result
from clovers_core.config import config as clovers_config
from .core.clovers import Event
from .core.manager import Manager
from .config import Config

config_key = __package__

config = Config.parse_obj(clovers_config.get(config_key, {}))
"""主配置类"""
clovers_config[config_key] = config.dict()
plugin = Plugin(
    build_event=lambda event: Event(event),
    build_result=lambda result: (
        Result("text", result) if isinstance(result, str) else Result("image", result) if isinstance(result, BytesIO) else result
    ),
)
"""小游戏插件实例"""
manager = Manager(config.main_path)
"""小游戏管理器实例"""
