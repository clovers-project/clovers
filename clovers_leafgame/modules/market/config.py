from pydantic import BaseModel


class Config(BaseModel):
    # 重置冷却时间，设置为0禁用发起重置
    revolt_cd: int = 28800
    # 重置的基尼系数
    revolt_gini: float = 0.68
    # 重置签到的范围
    revolt_gold: tuple[int, int] = (1000, 2000)
    # 最大赌注
    company_public_gold: int = 20000
