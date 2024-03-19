from pydantic import BaseModel


class Config(BaseModel):
    # 抽卡所需金币
    gacha_gold: int = 50
    # 礼包金币范围
    packet_gold: tuple[int, int] = (200, 2000)
    # 幸运硬币赌注范围
    luckey_coin: tuple[int, int] = (2000, 100000)
