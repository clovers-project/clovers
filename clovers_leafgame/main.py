"""小游戏运行实例"""

from pathlib import Path
from io import BytesIO
from clovers_core.plugin import Plugin, Result

from .core.clovers import Event
from .core.manager import Manager
from .core.config import Config

config_file = Path() / "LiteGames" / "config.toml"
"""配置路径"""
config = Config.load(config_file)
"""主配置类"""
main_path = config.main_path
plugin = Plugin(
    build_event=lambda event: Event(event),
    build_result=lambda result: (
        Result("text", result) if isinstance(result, str) else Result("image", result) if isinstance(result, BytesIO) else result
    ),
)
"""小游戏插件实例"""
manager = Manager(Path(main_path) / "russian_data.json")
"""小游戏管理器实例"""
