import toml
import os
from pathlib import Path
from functools import cache
from .logger import logger

CONFIG_FILE = os.environ.get("CLOVERS_CONFIG_FILE", "clovers.toml")


class Config(dict):
    @classmethod
    def load(cls, path: str | Path = CONFIG_FILE):
        logger.debug(f"loading config from {path}")
        path = Path(path) if isinstance(path, str) else path
        if path.exists():
            config = cls(toml.load(path))
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            config = cls()
        return config

    def save(self, path: str | Path = CONFIG_FILE):
        logger.debug(f"saving config to {path}")
        path = Path(path) if isinstance(path, str) else path
        parent = path.parent
        if not parent.exists():
            parent.mkdir(exist_ok=True, parents=True)
        with open(path, "w", encoding="utf8") as f:
            toml.dump(self, f)

    @classmethod
    @cache
    def environ(cls):
        return cls.load(CONFIG_FILE)


config = Config.environ()
