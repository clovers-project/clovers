from pydantic import BaseModel


class Config(BaseModel):
    gacha_gold: int = 50
