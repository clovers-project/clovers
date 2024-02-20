import toml
from pydantic import BaseModel
from pathlib import Path


class Config(BaseModel):
    @classmethod
    def load(cls, path: Path):
        if path.exists():
            config = cls.parse_obj(toml.load(path))
        else:
            path.parent.mkdir(exist_ok=True, parents=True)
            config = cls()
            config.save(path)
        return config

    def save(self, path: Path):
        with open(path, "w", encoding="utf8") as f:
            toml.dump(self.dict(), f)
