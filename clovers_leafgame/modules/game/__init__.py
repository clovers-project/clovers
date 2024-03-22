import random
from pathlib import Path
from datetime import datetime
from PIL import ImageColor
from collections import Counter
from clovers_utils.tools import download_url, format_number
from clovers_leafgame.core.clovers import Event, Check
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import (
    GOLD,
    STD_GOLD,
    LICENSE,
    CLOVERS_MARKING,
    REVOLUTION_MARKING,
    DEBUG_MARKING,
)
from clovers_leafgame.output import (
    text_to_image,
    endline,
    candlestick,
    bank_card,
    prop_card,
    invest_card,
    avatar_card,
    dist_card,
)
from .core import Session, Game, to_int
from clovers_core.config import config as clovers_config
from .config import Config

config = Config.parse_obj(clovers_config.get(__package__, {}))

place: dict[str, Session] = {}

russian_roulette = Game("俄罗斯轮盘")


@plugin.handle({"俄罗斯轮盘", "装弹"}, {"user_id", "group_id", "nickname", "at"})
@russian_roulette.create(place)
async def _(session: Session, arg: str):
    bullet_num = to_int(arg)
    if bullet_num:
        bullet_num = random.randint(1, 6) if bullet_num < 1 or bullet_num > 6 else bullet_num
    else:
        bullet_num = 1
    bullet = [0, 0, 0, 0, 0, 0]
    for i in random.sample([0, 1, 2, 3, 4, 5, 6], bullet_num):
        bullet[i] = 1
    session.data = {"bullet": bullet, "index": 0}
    if session.bet:
        prop, n = session.bet
        tip = f"\n本场赌注：{prop.name} {n}"
    else:
        tip = ""
    tip += f"\n第一枪的概率为：{round(bullet_num * 100 / 7,2)}%"
    return f"{' '.join('咔' for _ in range(bullet_num))}，装填完毕{tip}\n{session.create_info()}"


@plugin.handle({"开枪"}, {"user_id", "group_id", "nickname", "at"})
@russian_roulette.action(place)
async def _(session: Session, arg: str):
    pass
