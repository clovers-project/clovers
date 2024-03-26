import json
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from collections import Counter

KeyMap = dict[str, str]


class Item(BaseModel):
    id: str
    name: str

    def deal(self, bank: Counter[str], unsettled: int):
        prop_id = self.id
        n = bank[prop_id]
        if unsettled < 0 and n < (-unsettled):
            return n or -1
        bank[prop_id] += unsettled


class User(BaseModel):
    id: str
    name: str = ""
    avatar_url: str = ""
    connect: str = ""
    bank: Counter[str] = Counter()
    invest: Counter[str] = Counter()
    extra: dict = {}
    accounts_map: KeyMap = {}
    """Find account ID from group_id"""
    message: list[str] = []

    def add_message(self, message: str):
        self.message.append(message)
        self.message = self.message[-30:]


class Account(BaseModel):
    user_id: str
    group_id: str
    name: str = ""
    sign_in: datetime | None = None
    bank: Counter[str] = Counter()
    extra: dict = {}

    @property
    def id(self):
        return f"{self.user_id}-{self.group_id}"


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
    color: str = "black"
    intro: str = ""
    tip: str = ""

    def __init__(self, id: str, **data) -> None:
        data.update({"id": id, "rare": int(id[0]), "domain": int(id[1]), "flow": int(id[2]), "number": int(id[3:])})
        super().__init__(**data)

    def locate_bank(self, user: User, account: Account):
        match self.domain:
            case 1:
                return account.bank
            case _:
                return user.bank

    def N(self, user: User, account: Account):
        return self.locate_bank(user, account)[self.id]


class Stock(Item):
    value: int = 0
    """全群资产"""
    floating: float = 0
    """浮动资产"""
    issuance: int = 0
    """股票发行量"""
    time: float
    """注册时间"""
    exchange: dict[str, tuple[int, float]] = {}
    """交易信息"""


class Group(BaseModel):
    id: str
    name: str | None = None
    avatar_url: str | None = None
    level: int = 1
    stock: Stock | None = None
    bank: Counter[str] = Counter()
    invest: Counter[str] = Counter()
    extra: dict = {}
    accounts_map: KeyMap = {}
    """Find account ID from user_id"""
    message: list[str] = []

    @property
    def nickname(self):
        return self.stock.name if self.stock else self.name or self.id


class DataBase(BaseModel):
    user_dict: dict[str, User] = {}
    group_dict: dict[str, Group] = {}
    account_dict: dict[str, Account] = {}
    extra: dict = {}

    @classmethod
    def load(cls, file: Path) -> "DataBase":
        if file.exists():
            with open(file, "r", encoding="utf8") as f:
                data = cls.parse_obj(json.load(f))
        else:
            data = cls()
        return data

    def register(self, account: Account):
        """注册个人账户"""
        user_id = account.user_id
        group_id = account.group_id
        account_id = account.id
        self.user(user_id).accounts_map[group_id] = account_id
        self.group(group_id).accounts_map[user_id] = account_id
        self.account_dict[account_id] = account

    def user(self, user_id: str):
        if user_id not in self.user_dict:
            self.user_dict[user_id] = User(id=user_id)

        return self.user_dict[user_id]

    def group(self, group_id: str):
        if group_id not in self.group_dict:
            self.group_dict[group_id] = Group(id=group_id)

        return self.group_dict[group_id]

    def cancel_account(self, account_id: str):
        """注销 account"""
        account = self.account_dict.get(account_id)
        if not account:
            return
        user_id = account.user_id
        group_id = account.group_id
        del self.account_dict[account_id]
        try:
            del self.user_dict[user_id].accounts_map[group_id]
        except Exception as e:
            print(e)
        try:
            del self.group_dict[group_id].accounts_map[user_id]
        except Exception as e:
            print(e)

    def cancel_user(self, user_id: str):
        """注销 user"""
        user = self.user_dict.get(user_id)
        if not user:
            return
        del self.user_dict[user_id]
        for group_id, account_id in user.accounts_map.items():
            try:
                del self.account_dict[account_id]
            except Exception as e:
                print(e)
            try:
                del self.group_dict[group_id].accounts_map[user_id]
            except Exception as e:
                print(e)

    def cancel_group(self, group_id: str):
        """注销 group"""
        group = self.group_dict.get(group_id)
        del self.group_dict[group_id]
        if not group:
            return
        for user_id, account_id in group.accounts_map.items():
            try:
                del self.account_dict[account_id]
            except Exception as e:
                print(e)
            try:
                del self.user_dict[user_id].accounts_map[group_id]
            except Exception as e:
                print(e)
