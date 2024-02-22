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
from .data import Bank, Account, User, Group, Account, DataBase
from .linecard import info_splicing, ImageList

UserAccount = tuple[User, Account]

RankKey = Callable[[str], int | float]


class Manager:
    data: DataBase
    main_path: Path

    def __init__(self, main_path: Path) -> None:
        self.main_path = Path(main_path)
        self.DATA_PATH = self.main_path / "russian_data.json"
        self.BG_PATH = Path(main_path) / "bg"
        self.BG_PATH.mkdir(exist_ok=True, parents=True)
        self.load()

    def save(self):
        with open(self.DATA_PATH, "w") as f:
            f.write(self.data.json(indent=4))

    def load(self):
        if self.DATA_PATH.exists():
            with open(self.DATA_PATH, "r", encoding="utf8") as f:
                self.data = DataBase.parse_obj(json.load(f))

    def info_card(self, info: ImageList, user_id: str, BG_type=None):
        extra = self.locate_user(user_id).extra
        BG_type = BG_type or extra.get("BG_type", "#FFFFFF99")
        BG_PATH = self.BG_PATH / f"{user_id}.png"
        if not BG_PATH.exists():
            BG_PATH = BG_PATH / "default.png"
        return info_splicing(info, BG_PATH, spacing=10, BG_type=BG_type)

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

    def group_wealths(self, group_id: str, prop_id: str) -> int:
        """
        群内总资产
        """
        group = self.group_search(group_id)
        if not group:
            return 0

        return group.bank.get(prop_id, 0) + sum(
            self.locate_user(user_id).connecting(group_id).bank.get(prop_id, 0) for user_id in group.namelist
        )

    def ranklist(
        self,
        namelist: set[str],
        key: RankKey,
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

    def gold_value(self, group_id: str, account: Account):
        return account.bank.get("1111", 0) * self.locate_group(group_id).level

    def stock_value(self, invest: Bank):
        i = 0.0
        for group_id, n in invest.items():
            stock = self.stock_search(group_id)
            i += stock.stock_value * n / stock.issuance
        return int(i)

    def rankkey(self, title) -> RankKey:
        match title:
            case "总金币":
                return lambda user_id: sum(
                    self.gold_value(group_id, account) for group_id, account in self.locate_user(user_id).accounts.items()
                )
            case "总资产":
                return lambda user_id: sum(
                    self.gold_value(group_id, account) + self.stock_value(account.invest)
                    for group_id, account in self.locate_user(user_id).accounts.items()
                )
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

    def namelist(self, group_name: str = None):
        if group_name:
            return set().union(*(group.namelist for group in self.data.group_dict.values()))
        else:
            group = self.group_search(group_name)
            if group:
                return group.namelist
