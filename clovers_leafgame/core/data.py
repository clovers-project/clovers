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


class LibraryError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class Library[ItemClass: Item]:
    _data: dict[str, ItemClass]
    _index: dict[str, str]

    def __init__(self, data: list[ItemClass] = None) -> None:
        self._index: dict[str, str] = {}
        if data:
            self.data = data
        else:
            self._data = {}

    @property
    def data(self):
        return list(self._data.values())

    @data.setter
    def data(self, data: list[ItemClass]):
        self._data = {item.id: item for item in data}
        self.index_update()

    def index_update(self):
        self._index.clear()
        self._index.update({v.name: k for k, v in self._data.items()})
        self._index.update({k: k for k in self._data})

    def search(self, name: str):
        item_id = self._index.get(name)
        if not item_id:
            return
        return self._data[item_id]

    def append(self, item: Item):
        if not (item.id and item.name):
            raise LibraryError("无法加入未完成的Item")
        if item.id in self._data:
            raise LibraryError(f"id:{item.id}已经存在")
        if item.name in self._data:
            raise LibraryError(f"name:{item.name}已经存在")
        self._data[item.id] = item
        self._index[item.name] = item.id

    def rename(self, item_id: str, item_name: str):
        item = self.search(item_id)
        if not item:
            raise LibraryError(f"未找到{item_id}")
        if item_name in self._data:
            raise LibraryError(f"name:{item.name}已经存在")
        del self._index[item.name]
        item.name = item_name
        self._index[item.name] = item.id

    def update(self, data: list[ItemClass]):
        self._data.update({item.id: item for item in data})
        self.index_update()


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
