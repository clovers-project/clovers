from clovers_core.adapter import Adapter
from clovers_core.plugin import PluginLoader
from clovers_core.config import Config as CloversConfig
from pathlib import Path


class Config(CloversConfig):
    plugins_list: list = []


src_path = Path() / "clovers"
config_path = src_path / "config.toml"

config = Config.load(config_path)

plugins_path = src_path / "plugins"
plugins_path.mkdir(exist_ok=True, parents=True)

loader = PluginLoader(plugins_path.absolute(), config.plugins_list)

adapter = Adapter()
adapter.plugins = loader.load_plugins()
