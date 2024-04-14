import random
import os
import json
from pathlib import Path
from collections.abc import Callable, Coroutine
from clovers.core.plugin import PluginError
from clovers_leafgame.core.clovers import Event
from clovers_leafgame.item import Prop, AIR
from clovers_leafgame.main import plugin, manager

library_file = Path(os.path.join(os.path.dirname(__file__), "./props_library.json"))
with open(library_file, "r", encoding="utf8") as f:
    for k, v in json.load(f).items():
        prop = Prop(k, **v)
        manager.props_library.set_item(prop.id, [prop.name], prop)

pool = {
    rare: [manager.props_library[name].id for name in name_list]
    for rare, name_list in {
        3: ["优质空气", "四叶草标记", "挑战徽章", "设置许可证", "初级元素"],
        4: ["高级空气", "钻石会员卡"],
        5: ["特级空气", "进口空气", "幸运硬币"],
        6: ["纯净空气", "钻石", "道具兑换券", "超级幸运硬币", "重开券"],
    }.items()
}
AIR_PACK = manager.props_library["空气礼包"]
RED_PACKET = manager.props_library["随机红包"]
DIAMOND = manager.props_library["钻石"]


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


def usage(prop_name: str, extra_args):
    def decorator(func: Callable[..., Coroutine]):
        prop = manager.props_library.get(prop_name)
        if not prop:
            raise PluginError(f"不存在道具{prop_name}，无法注册使用方法。")

        @plugin.handle(f"使用(道具)?\\s*{prop_name}\\s*(\\d*)(.*)", extra_args)
        async def _(event: Event):
            _, count, extra = event.args
            return await func(prop, event, int(count) if count else 1, extra)

    return decorator
