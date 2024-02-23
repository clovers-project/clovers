"""+++++++++++++++++
————————————————————
    ᕱ⑅ᕱ。 ᴍᴏʀɴɪɴɢ
   (｡•ᴗ-)_
————————————————————
+++++++++++++++++"""

import json
from datetime import datetime, timedelta
from pydantic import BaseModel
from pathlib import Path
from collections.abc import Callable
from collections import Counter
from sys import platform

from .clovers import Event
from .data import Bank, Library, Account, User, Group, Account, DataBase, Stock
from .linecard import info_splicing, ImageList

UserAccount = tuple[User, Account]

RankKey = Callable[[str], int | float]


class Manager:
    data: DataBase
    main_path: Path
    stocks_library: Library[Stock]

    def __init__(self, main_path: Path) -> None:
        self.main_path = Path(main_path)
        self.DATA_PATH = self.main_path / "russian_data.json"
        self.BG_PATH = Path(main_path) / "BG_image"
        self.BG_PATH.mkdir(exist_ok=True, parents=True)
        self.load()

    def save(self):
        with open(self.DATA_PATH, "w") as f:
            f.write(self.data.json(indent=4))

    def load(self):
        if self.DATA_PATH.exists():
            with open(self.DATA_PATH, "r", encoding="utf8") as f:
                self.data = DataBase.parse_obj(json.load(f))
        else:
            self.data = DataBase()
        self.stocks_library = Library()
        self.stocks_library.data = [stock for group in self.data.group_dict.values() if (stock := group.stock)]

    def info_card(self, info: ImageList, user_id: str, BG_type=None):
        extra = self.locate_user(user_id).extra
        BG_type = BG_type or extra.get("BG_type", "#FFFFFF99")
        BG_PATH = self.BG_PATH / f"{user_id}.png"
        if not BG_PATH.exists():
            BG_PATH = self.BG_PATH / "default.png"
        return info_splicing(info, BG_PATH, spacing=10, BG_type=BG_type)

    def group_search(self, gruup_name: str):
        return self.data.group_dict.get(stock.id if (stock := self.stocks_library.search(gruup_name)) else gruup_name)

    def locate_group(self, group_id: str) -> Group:
        """
        定位群组
        """
        return self.data.group_dict.setdefault(group_id, Group(group_id=group_id))

    def locate_user(self, user_id: str) -> User:
        """
        定位用户
        """
        return self.data.user_dict.setdefault(user_id, User(user_id=user_id))

    def locate_account(self, user_id: str, group_id: str) -> UserAccount:
        """
        定位账户
        """
        user = self.locate_user(user_id)
        group = self.locate_group(group_id)
        group.namelist.add(user_id)
        return user, user.connecting(group_id)

    def account(self, event: Event) -> UserAccount:
        """
        定位账户
        """
        user_id = event.user_id
        user = self.locate_user(user_id)
        if event.is_private():
            user.name = event.nickname
            return user, user.connecting()
        if not user.name:
            user.name = event.nickname
        group_id = event.group_id
        group = self.locate_group(group_id)
        group.namelist.add(user_id)
        account = user.connecting(group_id)
        account.nickname = event.nickname
        return user, account

    def group_wealths(self, group_id: str, prop_id: str) -> list[int]:
        """
        群内总资产
        """
        group = self.group_search(group_id)
        if not group:
            return 0
        wealths = [self.locate_user(user_id).connecting(group_id).bank.get(prop_id, 0) for user_id in group.namelist]
        wealths.append(group.bank.get(prop_id, 0))
        return wealths

    def namelist(self, group_name: str = None):
        if group_name:
            group = self.group_search(group_name)
            if group:
                return group.namelist
        else:
            return set().union(*(group.namelist for group in self.data.group_dict.values()))

    def stock_value(self, invest: Bank):
        i = 0.0
        for group_id, n in invest.items():
            stock = self.stocks_library.search(group_id)
            i += stock.stock_value * n / stock.issuance
        return int(i)

    def ranklist(
        self,
        namelist: set[str],
        key: str,
        reverse: bool = True,
    ):
        """
        用户排行榜
            param:
                key:从用户寻找可以排名的排名内容
        """
        data = [(k, v) for k in namelist if (v := key(k))]
        data.sort(key=lambda x: x[1], reverse=reverse)
        return data

    def rankkey(self, title) -> RankKey:
        match title:
            case "胜场":
                return lambda user_id: self.locate_user(user_id).extra.setdefault("win", 0)
            case "连胜":
                return lambda user_id: self.locate_user(user_id).extra.setdefault("win_achieve", 0)
            case "败场":
                return lambda user_id: self.locate_user(user_id).extra.setdefault("lose", 0)
            case "败场":
                return lambda user_id: self.locate_user(user_id).extra.setdefault("lose_achieve", 0)
            case _:
                return
