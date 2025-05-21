import toml
import os
from pathlib import Path
from functools import cache
from .logger import logger

CONFIG_FILE = os.environ.get("CLOVERS_CONFIG_FILE", "clovers.toml")
"""默认 clovers 配置文件路径，从环境变量 CLOVERS_CONFIG_FILE 获取"""


class Config(dict):
    """clovers 配置类"""

    @classmethod
    def load(cls, path: str | Path = CONFIG_FILE):
        """加载配置文件

        配置文件为 toml 格式

        Args:
            path (str | Path, optional): 配置文件路径. Defaults to CONFIG_FILE.
        """

        logger.debug(f"loading config from {path}")
        path = Path(path) if isinstance(path, str) else path
        if path.exists():
            config = cls(toml.load(path))
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            config = cls()
        return config

    def save(self, path: str | Path = CONFIG_FILE):
        """保存配置文件

        将配置保存为 toml 文件

        Args:
            path (str | Path, optional): 配置文件路径. Defaults to CONFIG_FILE.
        """

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
        """获取默认配置"""
        return cls.load(CONFIG_FILE)
