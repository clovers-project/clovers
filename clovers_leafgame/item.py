"""
小游戏框架基础道具实例
    AIR:空气
    GOLD:金币
    VIP_CARD:钻石会员卡
    LICENSE:设置许可证
"""

import os
import json
from pathlib import Path
from .core.data import Prop
from clovers.utils.library import Library


def item_name_rule(item_name: str):
    if " " in item_name or "\n" in item_name:
        return "名称不能含有空格或回车"
    count = 0
    for x in item_name:
        if ord(x) < 0x200:
            count += 1
        else:
            count += 2
    if count > 24:
        return f"名称不能超过24字符"
    try:
        int(item_name)
        return f"名称不能是数字"
    except:
        return None


props_library_file = Path(os.path.join(os.path.dirname(__file__), "props_library.json"))
props_library: Library[str, Prop] = Library()
with open(props_library_file, "r", encoding="utf8") as f:
    for k, v in json.load(f).items():
        prop = Prop(k, **v)
        props_library.set_item(prop.id, [prop.name], prop)

AIR = props_library["空气"]
GOLD = props_library["金币"]
STD_GOLD = props_library["标准金币"]
VIP_CARD = props_library["钻石会员卡"]
LICENSE = props_library["设置许可证"]
CLOVERS_MARKING = props_library["四叶草标记"]
REVOLUTION_MARKING = props_library["路灯挂件标记"]
DEBUG_MARKING = props_library["Debug奖章"]
PROP_FOR_TEST = props_library["测试金库"]

marking_library: Library[str, Prop] = Library()
marking_library.set_item(PROP_FOR_TEST.id, [PROP_FOR_TEST.name], PROP_FOR_TEST)
marking_library.set_item(AIR.id, [AIR.name], AIR)
