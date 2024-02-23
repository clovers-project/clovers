import random
import os
import json
from pathlib import Path
from clovers_leafgame.prop import Prop, library, AIR

library_file = Path(os.path.join(os.path.dirname(__file__), "./props_library.json"))

with open(library_file, "r", encoding="utf8") as f:
    library.update(Prop(id=k, **v) for k, v in json.load(f).items())

pool = {
    rare: [library.search(name).id for name in name_list]
    for rare, name_list in {
        3: ["优质空气", "四叶草标记", "挑战徽章", "设置许可证", "初级元素"],
        4: ["高级空气", "铂金会员卡"],
        5: ["特级空气", "进口空气", "10%结算补贴", "10%额外奖励", "神秘天平", "幸运硬币"],
        6: ["纯净空气", "钻石", "道具兑换券", "超级幸运硬币", "重开券"],
    }.items()
}
AIR_PACK = library.search("空气礼包")
RED_PACK = library.search("随机红包")


def gacha() -> str:
    """
    随机获取道具。
        return: object_code
    """
    rand = random.uniform(0.0, 1.0)
    prob_list = (0.3, 0.1, 0.1, 0.02)
    rare = 3
    for prob in prob_list:
        rand -= prob
        if rand <= 0:
            break
        rare += 1
    if rare_pool := pool.get(rare):
        return random.choice(rare_pool)
    return AIR.id
