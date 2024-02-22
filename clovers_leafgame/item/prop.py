"""
道具类:Prop,Item子类
运行时

Library实例
    library:道具储存库
小游戏框架基础道具实例
    AIR:空气
    GOLD:金币
    VIP_CARD:钻石会员卡
    LICENSE:设置许可证
"""

import os
import json
from pathlib import Path
from ..core.data import Item, Library


class Prop(Item):
    rare: int
    """稀有度"""
    domain: int
    """
    作用域   
        0:无(空气)
        1:群内
        2:全局
    """
    flow: int
    """
    道具时效
        0:永久道具
        1:时效道具
    """
    number: int
    """道具编号"""

    def __init__(
        self,
        id: str,
        name: str,
        color: str,
        intro: str,
        tip: str,
    ) -> None:
        self.id = id
        self.name = name
        self.color: str = color
        self.intro: str = intro
        self.tip: str = tip
        self.rare, self.domain, self.flow, self.number = self.code_info()

    def code_info(self):
        rare = int(self.id[0])
        domain = int(self.id[1])
        flow = int(self.id[2])
        number = int(self.id[3:])
        return rare, domain, flow, number


library: Library[Prop] = Library()

library_file = Path(os.path.join(os.path.dirname(__file__), "./props_library.json"))

with open(library_file, "r", encoding="utf8") as f:
    library.data = {k: Prop(k, **v) for k, v in json.load(f).items()}

AIR = library.search("空气")
GOLD = library.search("金币")
VIP_CARD = library.search("钻石会员卡")
LICENSE = library.search("设置许可证")
