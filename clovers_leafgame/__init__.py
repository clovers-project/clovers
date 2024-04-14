from .main import plugin as __plugin__
from pathlib import Path
from clovers.core.plugin import PluginLoader

for x in (Path(__file__).parent / "modules").iterdir():
    name = x.stem if x.is_file() and x.name.endswith(".py") else x.name
    PluginLoader.load(f"{__package__}.modules.{name}")
