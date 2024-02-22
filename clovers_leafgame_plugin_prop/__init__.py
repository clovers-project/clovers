import random
import math
import re
import asyncio
from pathlib import Path
from datetime import datetime
from collections import Counter

from clovers_core.plugin import Result
from clovers_leafgame.core.clovers import Event, to_me
from clovers_leafgame.core.utils import to_int
from clovers_leafgame.main import config_file, plugin, manager
from clovers_leafgame.main import config as main_config
from clovers_leafgame.item.prop import GOLD
from .library import library, gacha
from .config import Config

config = Config.load(config_file)
gacha_gold = config.gacha_gold


@plugin.handle(r"^.+连抽?卡?|单抽", {"user_id", "group_id", "nickname", "to_me"})
@to_me.wrapper
async def _(event: Event) -> Result:
    N = re.search(r"^(.*)连抽?卡?$", event.raw_event.raw_command)
    if not N:
        return
    N = to_int(N.group(1))
    if not N:
        return
    N = 200 if N > 200 else 1 if N < 1 else N
    gold = N * gacha_gold
    user_id = event.user_id
    user = manager.locate_user(user_id)
    group_id = event.group_id or user.connect
    if n := user.deal(group_id, GOLD, -gold):
        return f"{N}连抽卡需要{gold}金币，你的金币：{n}。"

    prop_data = {0: [], 1: [], 2: []}
    report_data = {"prop_star": 0, "prop_n": 0, "air_star": 0, "air_n": 0}
    gacha_result = ((item, n) for item_id, n in Counter(gacha() for _ in range(N)).items() if n != 0 and (item := library.search(item_id)))
    for seg in gacha_result:
        prop_data[prop.domain].append(seg)
        prop, n = seg
        if prop.domain == 0:
            report_star = report_data["air_star"]
            report_n = report_data["air_n"]
        else:
            user.deal(group_id, prop, n)
            report_star = report_data["prop_star"]
            report_n = report_data["prop_n"]

        report_star += prop.rare * n
        report_n += n
    if report_data["prop_n"] == 0:
        user.deal(group_id, GOLD, gold)
        user.deal(group_id, AIR_PACK, 1)
        info.append(prop_card([(AIR_PACK, 1)], f"本次抽卡已免费（{gold}金币）"))        
    info = gacha_card(user.nickname(group_id), **report_data)

    return info_card(gacha_card(user.nickname(group_id), **report_data), user_id)

    if data := prop_data[2]:
        info.append(prop_card(data, "全局道具"))
    if data := prop_data[1]:
        info.append(prop_card(data, "群内道具"))
    if data := prop_data[0]:
        info.append(prop_card(data, "未获取"))
    return info_card(info, user_id)
