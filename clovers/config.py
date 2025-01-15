import toml
import os
from pathlib import Path
from functools import cache

CONFIG_FILE = os.environ.get("CLOVERS_CONFIG_FILE", "clovers.toml")


class Config(dict):
    @classmethod
    def load(cls, path: str | Path = CONFIG_FILE):
        print("加载中...")
        path = Path(path) if isinstance(path, str) else path
        if path.exists():
            config = cls(toml.load(path))
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            config = cls()
        return config

    def save(self, path: str | Path = CONFIG_FILE):
        path = Path(path) if isinstance(path, str) else path
        if not path.exists():
            path.parent.mkdir(exist_ok=True, parents=True)
        with open(path, "w", encoding="utf8") as f:
            toml.dump(self, f)

    @classmethod
    @cache
    def environ(cls):
        return cls.load(CONFIG_FILE)


config = Config.environ()
