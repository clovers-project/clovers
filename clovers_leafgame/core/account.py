import json
import time
from datetime import datetime, timedelta
from pydantic import BaseModel
from pathlib import Path
from collections.abc import Callable
from collections import Counter
from sys import platform

from clovers_core.plugin import Result
from .clovers import Event
from .data import Bank, Prop, Stock, Account, User, Group, Account, DataBase

UserAccount = tuple[User, Account]

RankKey = Callable[[str], int | float]


class Manager:
    """+++++++++++++++++
    ————————————————————
      ᕱ⑅ᕱ。 ᴍᴏʀɴɪɴɢ
     (｡•ᴗ-)_
    ————————————————————
    +++++++++++++++++"""

    data: DataBase
    file_path: Path
    extra: dict = {}
    group_index: dict[str, str] = {}

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.load()
        self.group_index_update()

    def save(self):
        with open(self.file_path, "w") as f:
            f.write(self.data.json(indent=4))

    def load(self):
        if self.file_path.exists():
            with open(self.file_path, "r") as f:
                self.data = DataBase.parse_obj(json.load(f))

    def group_index_update(self):
        d = self.data.group_dict
        self.group_index.clear()
        self.group_index.update({k: k for k in d})
        self.group_index.update({i: k for k, v in d.items() if (i := v.stock.name)})

    def group_search(self, group_name: str, retry: bool = True) -> Group:
        group_id = self.group_index.get(group_name)
        if group_id:
            return self.data.group_dict[group_id]
        if retry:
            self.group_index_update()
            return self.group_search(group_name, False)

    def stock_search(self, stock_name: str):
        if group := self.group_search(stock_name):
            return group.stock

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
            self.locate_user(user_id).connecting(group_id).bank.get(prop_id, 0)
            for user_id in group.namelist
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
