import sys
import importlib
from pathlib import Path


class PluginLoader:
    def __init__(self, plugins_path: Path, plugins_list: list) -> None:
        self.plugins_path: Path = plugins_path
        self.plugins_list: list = plugins_list

    @staticmethod
    def load(name: str):
        print(f"【leafgame loading plugin】 {name} ...")
        importlib.import_module(name)

    def load_plugins_from_path(self):
        plugins_raw_path = str(self.plugins_path)
        sys.path.insert(0, plugins_raw_path)
        plugins = []
        for x in self.plugins_path.iterdir():
            name = x.stem if x.is_file() and x.name.endswith(".py") else x.name
            if name.startswith("_"):
                continue
            plugins.append(self.load(name))
        sys.path = [path for path in sys.path if path != plugins_raw_path]
        return [plugin for plugin in plugins if plugin]

    def load_plugins_from_list(self):
        plugins = []
        for x in self.plugins_list:
            plugins.append(self.load(x))
        return [plugin for plugin in plugins if plugin]
