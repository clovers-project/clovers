import os
import json
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Union

resource_file = Path(os.path.dirname(__file__))


with open(resource_file / "props_library.json", "r", encoding="utf8") as f:
    props_library: dict = json.load(f)

Bank = dict[str, int]


class Stock(BaseModel):
    id: str = None
    name: str = None
    time: float = 0.0
    """注册时间"""
    issuance: int = 0
    """股票发行量"""


class Account(BaseModel):
    """
    用户群账户
    """

    gold: int
    nickname: str = None
    revolution: bool = False
    props: Bank = Bank()
    """更名为bank"""
    bank: Bank = Bank()
    invest: Bank = Bank()
    extra: dict = {}


class User(BaseModel):
    """
    用户数据
    """

    user_id: str = None
    nickname: str = None
    """更名为name"""
    name: str = None
    avatar_url: str = None
    win: int = 0
    lose: int = 0
    Achieve_win: int = 0
    Achieve_lose: int = 0

    gold: int = 0
    """存入bank"""
    group_accounts: dict[str, Account] = {}
    accounts: dict[str, Account] = {}
    connect: str | None | int = None
    props: Bank = Bank()
    """更名为bank"""
    bank: Bank = Bank()
    extra: dict = {}


class Company(BaseModel):
    """
    公司账户
    """

    company_id: str = None
    """群号"""
    company_name: str | None = None
    """公司名称"""
    level: int = 1
    """公司等级"""
    time: float = 0.0
    """注册时间"""
    stock: Union[int, Stock] = Stock()
    """正在发行的股票数"""
    issuance: int = 0
    """股票发行量"""
    gold: float = 0.0
    """固定资产"""
    float_gold: float = 0.0
    """浮动资产"""
    group_gold: float = 0.0
    """全群资产"""
    bank: int = 0
    """群金币，存入group bank字段"""
    invest: dict[str, int] = {}
    """群投资"""
    transfer_limit: float = 0.0
    """每日转账限制"""
    transfer: int = 0
    """今日转账额"""
    intro: str | None = None
    """群介绍"""
    orders: dict = {}
    """当前订单"""


class Group(BaseModel):
    """
    群字典
    """

    group_id: str = None
    namelist: set = set()
    revolution_time: float = 0.0
    """存入extra"""
    Achieve_revolution: dict[str, int] = {}
    """存入extra"""
    company: Company = Company()
    """已取消"""
    stock: Stock = Stock()
    level: int = 1
    bank: Bank = Bank()
    invest: Bank = Bank()
    intro: Union[str, None] = None
    """群介绍"""
    extra: dict = {}


class DataBase(BaseModel):
    user: dict[str, User] = {}
    group: dict[str, Group] = {}

    user_dict: dict[str, User] = {}
    group_dict: dict[str, Group] = {}

    def save(self, file):
        """
        保存数据
        """
        with open(file, "w", encoding="utf8") as f:
            f.write(self.model_dump_json(indent=4))

    @classmethod
    def loads(cls, data: str):
        """
        从json字符串中加载数据
        """

        return cls.model_validate_json(data)


data_file = resource_file / "russian_data.json"
with open(data_file, "r") as f:
    data = DataBase.loads(f.read())


def recode(code: str):
    rare = int(code[0])
    domain = int(code[1])
    flow = int(code[2])
    number = code[3:]
    if number[0] == "0":
        domain -= 1

    number = int(number)
    return f"{rare}{domain}{flow}{number}"


for user in data.user.values():
    for group_id, group_account in user.group_accounts.items():
        group_account.props = {recode(k): v for k, v in group_account.props.items()}
        group_account.bank = group_account.props
        group_account.bank["1111"] = group_account.gold
        user.accounts[group_id] = group_account
        user.extra["win"] = user.win
        user.extra["win_achieve"] = user.Achieve_win
        user.extra["lose"] = user.lose
        user.extra["lose_achieve"] = user.Achieve_lose
    user.name = user.nickname
    user.bank = user.props

for group in data.group.values():
    company = group.company
    group.bank["1111"] = company.bank
    group.invest = company.invest
    group.level = company.level
    group.intro = company.intro
    group.stock = Stock()
    group.stock.time = company.time
    group.extra["revolution_achieve"] = group.Achieve_revolution
    group.extra["revolution_time"] = group.revolution_time
data.group_dict = data.group
data.user_dict = data.user

data.save(data_file)
