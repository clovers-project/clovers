from datetime import datetime
from pydantic import BaseModel

KeyMap = dict[str, str]

Bank = dict[str, int]


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
    level: int = 1
    bank: Bank = Bank()
    invest: Bank = Bank()
    intro: str = None
    extra: dict = {}
    accounts_map: KeyMap = {}
    """Find account ID from user_id"""


class Account(BaseModel):
    user_id: str
    group_id: str
    name: str = None
    sign_date: datetime = None
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
        return self.user_dict.setdefault(user_id, User(id=user_id))

    def group(self, group_id: str):
        return self.group_dict.setdefault(group_id, Group(id=group_id))

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


class Item(BaseModel):
    id: str = None
    name: str = None

    def deal(self, bank: Bank, unsettled: int):
        prop_id = self.id
        n = bank.get(prop_id, 0)
        if unsettled < 0 and n < (-unsettled):
            return n or -1
        bank[prop_id] = n + unsettled
