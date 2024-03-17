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
from clovers_utils.linecard import info_splicing, ImageList
from clovers_utils.library import Library
from .core.clovers import Event
from .core.data import Bank, Account, User, Group, Account, DataBase
from .item import Prop, props_library, marking_library, VIP_CARD


class Manager:
    data: DataBase
    main_path: Path

    def __init__(self, main_path: Path) -> None:
        self.main_path = Path(main_path)
        self.DATA_PATH = self.main_path / "russian_data.json"
        self.BG_PATH = self.main_path / "BG_image"
        self.BG_PATH.mkdir(exist_ok=True, parents=True)
        self.backup_path = self.main_path / "backup"
        self.backup_path.mkdir(exist_ok=True, parents=True)
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
            if stock_name := group.stock.name:
                self.group_library.set_item(group.id, {stock_name}, group)
            else:
                self.group_library[group.id] = group

    def backup(self):
        now = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        date_today, now_time = now.split()
        backup_today = self.backup_path / date_today
        if not backup_today.exists():
            backup_today.mkdir()
        self.save()
        file = backup_today / f"russian_data {now_time}.json"
        file.write_text(self.data.json(indent=4))

    def clean_backup(self, delta: int | float):
        folders = [f for f in self.backup_path.iterdir() if f.is_dir()]
        info = []
        for folder in folders:
            if datetime.now().timestamp() - folder.stat().st_birthtime > delta:
                folder.unlink(True)
                info.append(f"备份 {folder} 已删除！")
        return "\n".join(info)

    def info_card(self, info: ImageList, user_id: str, BG_type=None):
        extra = self.data.user(user_id).extra
        BG_type = BG_type or extra.get("BG_type", "#FFFFFF99")
        BG_PATH = self.BG_PATH / f"{user_id}.png"
        if not BG_PATH.exists():
            BG_PATH = self.BG_PATH / "default.png"
        return info_splicing(info, BG_PATH, spacing=10, BG_type=BG_type)

    def new_account(self, user_id: str, group_id: str, **kwargs):
        account = Account(user_id=user_id, group_id=group_id, sign_in=datetime.today() - timedelta(days=1), **kwargs)
        self.data.register(account)
        return account

    def locate_account(self, user_id: str, group_id: str):
        user = self.data.user(user_id)
        account_id = user.accounts_map.get(group_id)
        if not (account_id and (account := self.data.account_dict.get(account_id))):
            account = self.new_account(user_id, group_id)
        return user, account

    def account(self, event: Event):
        """
        定位账户
        """
        user_id = event.user_id
        user = self.data.user(user_id)
        group_id = event.group_id or user.connect
        account_id = user.accounts_map.get(group_id)
        if not (account_id and (account := self.data.account_dict.get(account_id))):
            account = self.new_account(user_id, group_id)
        if not user.name or event.is_private():
            user.name = event.nickname
        account.name = event.nickname
        return user, account

    def transfer(
        self,
        prop: Prop,
        unsettled: int,
        sender_id: str,
        receiver_id: str,
        group_id: str,
    ):
        sender, sender_account = self.locate_account(sender_id, group_id)
        receiver, receiver_account = self.locate_account(receiver_id, group_id)
        if prop.domain == 1:
            sender_bank = sender_account.bank
            receiver_bank = receiver_account.bank
        else:
            sender_bank = sender.bank
            receiver_bank = receiver.bank
        sender_name = sender_account.name or sender.name or sender.id
        if n := prop.deal(sender_bank, -unsettled):
            return f"数量不足。\n——{sender_name}还有{n}个{prop.name}。"
        receiver_name = receiver_account.name or receiver.name or receiver.id
        if sender_account.bank.get(VIP_CARD.id):
            tax = 0
            tip = f"『{VIP_CARD.name}』免手续费"
        else:
            tax = int(unsettled * 0.02)
            tip = f"扣除2%手续费：{tax}，实际到账{prop.name}数{unsettled - tax}"
        prop.deal(receiver_bank, unsettled - tax)
        prop.deal(self.data.group(group_id).bank, tax)
        return f"{sender_name} 向 {receiver_name} 赠送{unsettled}个{prop.name}\n{tip}"

    def group_wealths(self, group_name: str, prop_id: str) -> list[int]:
        """
        群内总资产
        """
        group = self.group_library.get(group_name)
        if not group:
            return []
        wealths = [self.data.account_dict[account_id].bank.get(prop_id, 0) for account_id in group.accounts_map.values()]
        wealths.append(group.bank.get(prop_id, 0))
        return wealths

    def stock_value(self, invest: Bank):
        i = 0.0
        for group_id, n in invest.items():
            group = self.data.group_dict.get(group_id)
            if not group or group.stock.name is None:
                invest[group_id] = 0
                continue
            stock = group.stock
            if stock.issuance > 0:
                i += stock.value * n / stock.issuance
        return int(i)

    @typing_extensions.deprecated("The `group_search` method is deprecated; use `group_library.get` instead.", category=None)
    def group_search(self, group_name: str):
        return self.group_library.get(group_name)

    @typing_extensions.deprecated("The `locate_group` method is deprecated; use `data.group` instead.", category=None)
    def locate_group(self, group_id: str) -> Group:
        return self.data.group(group_id)

    @typing_extensions.deprecated("The `locate_user` method is deprecated; use `data.user` instead.", category=None)
    def locate_user(self, user_id: str) -> User:
        return self.data.user(user_id)
