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
from clovers_leafgame_core.data import Prop
from clovers_utils.library import Library

# def user_bank(self, user: User, group_id: str):
#     match self.domain:
#         case 1:
#             return user
#         case _:
#             return user.bank

# def user_N(self, user: User, group_id: str):
#     return self.user_bank(user, group_id)[self.id, 0)

# def deal_with(self, user: User, group_id: str, unsettled: int):
#     return self.deal(self.user_bank(user, group_id), unsettled)


props_library_file = Path(os.path.join(os.path.dirname(__file__), "./props_library.json"))
props_library: Library[str, Prop] = Library()
with open(props_library_file, "r", encoding="utf8") as f:
    for k, v in json.load(f).items():
        prop = Prop(id=k, **v)
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
