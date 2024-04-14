import os
import toml
from pathlib import Path


class Config(dict):
    path: Path

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.exists():
            config = cls(toml.load(path))
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            config = cls()
        config.path = path
        return config

    def save(self):
        with open(self.path, "w", encoding="utf8") as f:
            toml.dump(self, f)


config = Config.load(os.environ.get("clovers_config_file", "clovers.toml"))
