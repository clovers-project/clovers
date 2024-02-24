"""
道具类:Prop,Item子类
运行时

Library实例
    props_library:道具储存库

小游戏框架基础道具实例
    AIR:空气
    GOLD:金币
    VIP_CARD:钻石会员卡
    LICENSE:设置许可证
"""

import os
import json
from pathlib import Path

from ..core.data import Library, Prop

library: Library[Prop] = Library()

library_file = Path(os.path.join(os.path.dirname(__file__), "./props_library.json"))

with open(library_file, "r", encoding="utf8") as f:
    library.update(Prop(id=k, **v) for k, v in json.load(f).items())

AIR = library.search("空气")
GOLD = library.search("金币")
STD_GOLD = library.search("标准金币")
VIP_CARD = library.search("钻石会员卡")
LICENSE = library.search("设置许可证")
CLOVERS_MARKING = library.search("四叶草标记")
REVOLUTION_MARKING = library.search("路灯挂件标记")
DEBUG_MARKING = library.search("Debug奖章")

marking_library: Library[Prop] = Library()
marking_library.append(library.search("测试金库"))
