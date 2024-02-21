from datetime import datetime, timedelta
from pydantic import BaseModel
from collections.abc import Callable, Coroutine


Bank = dict[str, int]


class Item:
    id: str = None
    name: str = None

    def deal(self, bank: Bank, unsettled: int):
        """
        账户结算
        """
        prop_id = self.id
        n = bank.get(prop_id, 0)
        if unsettled < 0 and n < (-unsettled):
            return n or -1
        bank[prop_id] = n + unsettled


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
        self.use: Callable = lambda *any, **other: f"{self.name}不是可用道具"

    def code_info(self):
        rare = int(self.id[0])
        domain = int(self.id[1])
        flow = int(self.id[2])
        number = int(self.id[3:])
        return rare, domain, flow, number

    def set_usage(self, **kwargs):
        def decorator(func: Callable):
            def wrapper(event):
                return func(self, event, **kwargs)

            self.use = wrapper

        return decorator


class Stock(Item, BaseModel):
    issuance: int = 0
    """股票发行量"""
    time: datetime = None
    """注册时间"""
    floating: int = 0
    """浮动资产"""
    fixed: int = 0
    """固定资产"""
    stock_value: int = 0
    """全群资产"""


class Account(BaseModel):
    """
    用户群账户
    """

    nickname: str = None
    sign_date: datetime = datetime.today() - timedelta(days=1)
    revolution: bool = False
    bank: Bank = Bank()
    invest: Bank = Bank()
    extra: dict = {}


class User(BaseModel):
    """
    用户数据
    """

    user_id: str = None
    name: str = None
    avatar_url: str = None
    accounts: dict[str, Account] = {}
    connect: str = None
    bank: Bank = Bank()
    extra: dict = {}

    def connecting(self, group_id: str = None) -> Account:
        """连接到账户"""
        group_id = group_id or self.connect
        return self.accounts.setdefault(group_id, Account(nickname=self.name))

    def locate_bank(self, group_id: str, domain: int):
        match domain:
            case 1:
                return self.connecting(group_id).bank
            case _:
                return self.bank

    def deal(self, group_id: str, prop: Prop, unsettled: int):
        return prop.deal(self.locate_bank(group_id, prop.domain), unsettled)

    def nickname(self, group_id: str = None):
        if group_id and (account := self.accounts.get(group_id)):
            return account.nickname or self.name
        return self.name


class Group(BaseModel):
    """
    群字典
    """

    group_id: str = None
    """群号"""
    namelist: set[str] = set()
    """群员名单"""
    stock: Stock = Stock()
    """发行ID"""
    level: int = 1
    """群等级"""
    bank: Bank = Bank()
    """群金库"""
    invest: Bank = Bank()
    """群投资"""
    intro: str = None
    """群介绍"""
    extra: dict = {}

    @property
    def name(self) -> str:
        return self.stock.name or self.group_id


class DataBase(BaseModel):
    user_dict: dict[str, User] = {}
    group_dict: dict[str, Group] = {}
