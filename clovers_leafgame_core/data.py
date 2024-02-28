from datetime import datetime
from pydantic import BaseModel

KeyMap = dict[str, str]

Bank = dict[str, int]


class Item(BaseModel):
    id: str = None
    name: str = None

    def deal(self, bank: Bank, unsettled: int):
        prop_id = self.id
        n = bank.get(prop_id, 0)
        if unsettled < 0 and n < (-unsettled):
            return n or -1
        bank[prop_id] = n + unsettled


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

    # def user_bank(self, user: User, group_id: str):
    #     match self.domain:
    #         case 1:
    #             return user
    #         case _:
    #             return user.bank

    # def user_N(self, user: User, group_id: str):
    #     return self.user_bank(user, group_id).get(self.id, 0)

    # def deal_with(self, user: User, group_id: str, unsettled: int):
    #     return self.deal(self.user_bank(user, group_id), unsettled)


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


class User(BaseModel):
    id: str
    name: str = None
    avatar_url: str = None
    connect: str = None
    bank: Bank = Bank()
    invest: Bank = Bank()
    extra: dict = {}
    accounts_map: KeyMap = {}
    """Find account ID from group_id"""


class Group(BaseModel):
    id: str
    name: str = None
    avatar_url: str = None
    stock: Stock = None
    bank: Bank = Bank()
    invest: Bank = Bank()
    extra: dict = {}
    accounts_map: KeyMap = {}
    """Find account ID from user_id"""

    @property
    def nickname(self):
        return self.stock.name if self.stock else self.name or self.id


class Account(BaseModel):
    user_id: str
    group_id: str
    name: str = None
    sign_in: datetime = None
    bank: Bank = Bank()
    extra: dict = {}

    @property
    def id(self):
        return f"{self.user_id}-{self.group_id}"


class DataBase(BaseModel):
    user_dict: dict[str, User] = {}
    group_dict: dict[str, Group] = {}
    account_dict: dict[str, Account] = {}

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
        del self.account_dict[account_id]
        user_id = account.user_id
        group_id = account.group_id
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
