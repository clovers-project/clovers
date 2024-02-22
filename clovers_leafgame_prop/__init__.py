import re
from collections import Counter

from clovers_leafgame.core.data import Prop
from clovers_leafgame.core.clovers import Event, to_me
from clovers_leafgame.core.utils import to_int
from clovers_leafgame.main import plugin, manager

from clovers_leafgame.prop import GOLD
from .library import library, gacha, AIR_PACK

from clovers_leafgame.output import prop_card
from .output import report_card

from clovers_core.config import config as clovers_config
from .config import Config

config_key = __package__
config = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config.dict()
clovers_config.save()

gacha_gold = config.gacha_gold


@plugin.handle(r"^.+连抽?卡?|单抽", {"user_id", "group_id", "nickname", "to_me"})
@to_me.wrapper
async def _(event: Event):
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
    if n := GOLD.deal_with(user, group_id, -gold):
        return f"{N}连抽卡需要{gold}金币，你的金币：{n}。"

    prop_data: dict[int, list[tuple[Prop, int]]] = {0: [], 1: [], 2: []}
    report_data = {"prop_star": 0, "prop_n": 0, "air_star": 0, "air_n": 0}
    for prop_id, n in Counter(gacha() for _ in range(N)).items():
        prop = library.search(prop_id)
        prop_data[prop.domain].append((prop, n))
        if prop.domain == 0:
            star_key = "air_star"
            n_key = "air_n"
        else:
            prop.deal_with(user, group_id, n)
            star_key = "prop_star"
            n_key = "prop_n"

        report_data[star_key] += prop.rare * n
        report_data[n_key] += n
    if N < 10:
        info = ["你获得了"]
        info += [f"({prop.rare}☆){prop.name}:{n}个" for prop, n in prop_data[0]]
        info += [f"({prop.rare}☆){prop.name}:{n}个" for prop, n in prop_data[1]]
        info += [f"({prop.rare}☆){prop.name}:{n}个" for prop, n in prop_data[2]]
        return "\n".join(info)
    else:
        info = [report_card(user.nickname(group_id), **report_data)]
        if report_data["prop_n"] == 0:
            AIR_PACK.deal_with(user, group_id, 1)
            GOLD.deal_with(user, group_id, gold)
            info.append(prop_card([(AIR_PACK, 1), (GOLD, gold)], f"本次抽卡已免费"))
        if data := prop_data[2]:
            info.append(prop_card(data, "全局道具"))
        if data := prop_data[1]:
            info.append(prop_card(data, "群内道具"))
        if data := prop_data[0]:
            info.append(prop_card(data, "未获取"))

    return manager.info_card(info, user_id)
