"""+++++++++++++++++
————————————————————
    ᕱ⑅ᕱ。 ᴍᴏʀɴɪɴɢ
   (｡•ᴗ-)_
————————————————————
+++++++++++++++++"""

import typing_extensions
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import Callable
from clovers_utils.linecard import info_splicing, ImageList
from clovers_utils.library import Library
from clovers_leafgame_core.clovers import Event
from clovers_leafgame_core.data import Bank, Account, User, Group, Account, DataBase
from .item import Prop, props_library, marking_library

RankKey = Callable[[str], int | float]


class Manager:
    data: DataBase
    main_path: Path

    def __init__(self, main_path: Path) -> None:
        self.main_path = Path(main_path)
        self.DATA_PATH = self.main_path / "russian_data.json"
        self.BG_PATH = Path(main_path) / "BG_image"
        self.BG_PATH.mkdir(exist_ok=True, parents=True)
        self.props_library = props_library
        self.marking_library = marking_library
        self.group_library: Library[str, Group] = Library()
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
        for group in self.data.group_dict.values():
            if stock := group.stock:
                self.group_library.set_item(group.id, {stock.name}, group)
            else:
                self.group_library[group.id] = group

    def info_card(self, info: ImageList, user_id: str, BG_type=None):
        extra = self.locate_user(user_id).extra
        BG_type = BG_type or extra.get("BG_type", "#FFFFFF99")
        BG_PATH = self.BG_PATH / f"{user_id}.png"
        if not BG_PATH.exists():
            BG_PATH = self.BG_PATH / "default.png"
        return info_splicing(info, BG_PATH, spacing=10, BG_type=BG_type)

    @typing_extensions.deprecated("The `group_search` method is deprecated; use `group_library.get` instead.", category=None)
    def group_search(self, group_name: str):
        return self.group_library.get(group_name)

    @typing_extensions.deprecated("The `locate_group` method is deprecated; use `data.group` instead.", category=None)
    def locate_group(self, group_id: str) -> Group:
        return self.data.group(group_id)

    @typing_extensions.deprecated("The `locate_user` method is deprecated; use `data.user` instead.", category=None)
    def locate_user(self, user_id: str) -> User:
        return self.data.user(user_id)

    def new_account(self, user_id: str, group_id: str, **kwargs):
        account = Account(user_id=user_id, group_id=group_id, sign_in=datetime.today() - timedelta(days=1), **kwargs)
        self.data.register(account)
        return account

    def locate_account(self, user_id: str, group_id: str):
        user = self.data.user(user_id)
        account_id = user.accounts_map.get(group_id)
        if not (account_id and (account := self.data.account(account_id))):
            account = self.new_account(user_id, group_id)
        return account

    def account(self, event: Event):
        """
        定位账户
        """
        user_id = event.user_id
        user = self.data.user(user_id)
        group_id = event.group_id or user.connect
        account_id = user.accounts_map.get(group_id)
        if not (account_id and (account := self.data.account(account_id))):
            account = self.new_account(user_id, group_id)
        if not user.name or event.is_private():
            user.name = event.nickname
        account.name = event.nickname
        return user, account

    def locate_bank(self, prop: Prop, user_id: str, group_id: str):
        match prop.domain:
            case 1:
                return self.locate_account(user_id, group_id).bank
            case _:
                return self.data.user(user_id).bank

    def deal(self, prop: Prop, user_id: str, group_id: str, unsettled: int):
        bank = self.locate_bank(prop, user_id, group_id)
        return prop.deal(bank, unsettled)

    def prop_number(self, prop: Prop, user_id: str, group_id: str):
        bank = self.locate_bank(prop, user_id, group_id)
        return bank.get(prop.id, 0)

    def group_wealths(self, group_name: str, prop_id: str) -> list[int]:
        """
        群内总资产
        """
        group = self.group_library.get(group_name)
        if not group:
            return 0
        wealths = [self.data.account(account_id).bank.get(prop_id, 0) for account_id in group.accounts_map]
        wealths.append(group.bank.get(prop_id, 0))
        return wealths

    @typing_extensions.deprecated("The `namelist` method is deprecated", category=None)
    def namelist(self, group_name: str = None):
        pass

    def stock_value(self, invest: Bank):
        i = 0.0
        for group_id, n in invest.items():
            group = self.data.group_dict.get(group_id)
            if not group or group.stock is None:
                invest[group_id] = 0
                continue
            stock = group.stock
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

    @typing_extensions.deprecated("The `rankkey` method is deprecated", category=None)
    def rankkey(self, title) -> RankKey:
        match title:
            case "胜场":
                return lambda locate_id: self.locate_user(locate_id).extra.setdefault("win", 0)
            case "连胜":
                return lambda locate_id: self.locate_user(locate_id).extra.setdefault("win_achieve", 0)
            case "败场":
                return lambda locate_id: self.locate_user(locate_id).extra.setdefault("lose", 0)
            case "败场":
                return lambda locate_id: self.locate_user(locate_id).extra.setdefault("lose_achieve", 0)
            case _:
                return
