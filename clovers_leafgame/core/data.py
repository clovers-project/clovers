from datetime import datetime, timedelta
from pydantic import BaseModel
from collections.abc import Callable, Coroutine

Bank = dict[str, int]


class Item(BaseModel):
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


class Account(BaseModel):
    """
    用户群账户
    """

    nickname: str = None
    sign_date: datetime = datetime.today() - timedelta(days=1)
    revolution: bool = False
    bank: Bank = Bank()
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
    invest: Bank = Bank()
    extra: dict = {}

    def connecting(self, group_id: str = None) -> Account:
        """连接到账户"""
        group_id = group_id or self.connect
        return self.accounts.setdefault(group_id, Account(nickname=self.name))

    def nickname(self, group_id: str = None):
        if group_id and (account := self.accounts.get(group_id)):
            return account.nickname or self.name
        return self.name


class Prop(Item):
    rare: int = None
    """稀有度"""
    domain: int = None
    """
    作用域   
        0:无(空气)
        1:群内
        2:全局
    """
    flow: int = None
    """
    道具时效
        0:永久道具
        1:时效道具
    """
    number: int = None
    """道具编号"""
    color: str = None
    intro: str = None
    tip: str = None

    def __init__(self, **data) -> None:
        super().__init__(**data)
        if self.id:
            self.rare, self.domain, self.flow, self.number = self.code_info()

    def code_info(self):
        rare = int(self.id[0])
        domain = int(self.id[1])
        flow = int(self.id[2])
        number = int(self.id[3:])
        return rare, domain, flow, number

    def user_bank(self, user: User, group_id: str):
        match self.domain:
            case 1:
                return user.connecting(group_id).bank
            case _:
                return user.bank

    def user_N(self, user: User, group_id: str):
        return self.user_bank(user, group_id).get(self.id, 0)

    def deal_with(self, user: User, group_id: str, unsettled: int):
        return self.deal(self.user_bank(user, group_id), unsettled)


class Stock(Item):
    issuance: int = 0
    """股票发行量"""
    time: float = None
    """注册时间"""
    floating: int = 0
    """浮动资产"""
    fixed: int = 0
    """固定资产"""
    stock_value: int = 0
    """全群资产"""


class Group(BaseModel):
    """
    群字典
    """

    group_id: str = None
    """群号"""
    stock: Stock = Stock()
    """群名"""
    namelist: set[str] = set()
    """群员名单"""
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

    @property
    def xfer_record(self) -> dict[str, int]:
        return self.extra.setdefault("xfers", {"record": 0, "limit": 0})

    def xfer_out(self, xfer: int):
        xfer_record = self.xfer_record
        limit = xfer_record["limit"]
        record = xfer_record["record"]
        if record <= -limit:
            return 0
        if limit < xfer - record:
            return limit + record
        return xfer

    def xfer_in(self, xfer: int):
        xfer_record = self.xfer_record
        limit = xfer_record["limit"]
        record = xfer_record["record"]
        if limit <= record:
            return 0
        if limit < record + xfer:
            return limit - record
        return xfer


class DataBase(BaseModel):
    user_dict: dict[str, User] = {}
    group_dict: dict[str, Group] = {}
