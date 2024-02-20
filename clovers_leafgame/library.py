import os
import json
import random
from pathlib import Path
from collections.abc import Callable, Coroutine
from .core.data import Prop, User
from .core.account import RankKey

resource_file = Path(os.path.join(os.path.dirname(__file__), "./resource"))


with open(resource_file / "props_library.json", "r", encoding="utf8") as f:
    props_library: dict[str, Prop] = {k: Prop(k, **v) for k, v in json.load(f).items()}

props_index = {}
props_index.update({v.name: k for k, v in props_library.items()})
props_index.update({k: k for k in props_library})


def prop_search(prop_name: str):
    if not (prop_code := props_index.get(prop_name)):
        return

    return props_library[prop_code]


GOLD = prop_search("金币")
VIP_CARD = prop_search("钻石会员卡")
RED_PACK = prop_search("随机红包")
AIR = prop_search("空气")
AIR_PACK = prop_search("空气礼包")
LICENSE = prop_search("设置许可证")

prop_pool = {}
prop_pool[3] = ["优质空气", "四叶草标记", "挑战徽章", "设置许可证", "初级元素"]
prop_pool[4] = ["高级空气", "铂金会员卡"]
prop_pool[5] = [
    "特级空气",
    "进口空气",
    "10%结算补贴",
    "10%额外奖励",
    "神秘天平",
    "幸运硬币",
]
prop_pool[6] = ["纯净空气", "钻石", "道具兑换券", "超级幸运硬币", "重开券"]

for k, v in prop_pool.items():
    prop_pool[k] = [prop_search(i).id for i in v]


def gacha() -> str:
    """
    随机获取道具。
        return: object_code
    """
    rand = random.uniform(0.0, 1.0)
    prob_list = [0.3, 0.1, 0.1, 0.02]
    rare = 3
    for prob in prob_list:
        rand -= prob
        if rand <= 0:
            break
        rare += 1
    if rare_pool := prop_pool.get(rare):
        return random.choice(rare_pool)
    return AIR.id
