import time
import math
import random
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import GOLD, STD_GOLD, LICENSE
from clovers_leafgame_core.clovers import Event, to_me, group_admin
from clovers_utils.tools import to_int, item_name_rule, gini_coef, format_number
from clovers_core.config import config as clovers_config
from .config import Config

config_key = __package__
config = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config.dict()


revolt_gold = config.revolt_gold
revolt_gini = config.revolt_gini
revolt_cd = config.revolt_cd
company_public_gold = config.company_public_gold


@plugin.handle({"重置签到", "领取金币"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event):
    user, account = manager.account(event)
    user.avatar_url = event.avatar
    extra = account.extra
    if extra.setdefault("revolution", False):
        return "你没有待领取的金币"
    N = random.randint(*revolt_gold)
    GOLD.deal(account.bank, N)
    extra["revolution"] = True
    return f"这是你重置后获得的金币！你获得了 {N} 金币"


def xfer_out(limit: int, record: int, xfer: int):
    if record <= -limit:
        return 0
    if limit < xfer - record:
        return limit + record
    return xfer


def xfer_in(limit: int, record: int, xfer: int):
    if limit <= record:
        return 0
    if limit < record + xfer:
        return limit - record
    return xfer


@plugin.handle({"金币转移"}, {"user_id", "group_id"})
async def _(event: Event):
    args = event.raw_event.args
    if len(args) != 1:
        return
    xfer = to_int(args[0])
    if not xfer:
        return
    user_id = event.user_id
    group_id = event.group_id
    user, account = manager.locate_account(user_id, group_id)
    group = manager.data.group(group_id)
    xfer_record = group.extra.setdefault("xfers", {"record": 0, "limit": 0})
    if xfer < 0:
        xfer = xfer_out(xfer_record["limit"], xfer_record["record"], -xfer)
        if not xfer:
            return f"本群转出金币已到达限制：{xfer_record['limit']}"
        if n := GOLD.deal(account.bank, -xfer):
            return f"数量不足。\n——你在本群还有{n}枚金币。"
        STD_GOLD.deal(user.bank, int(xfer * group.level))
        xfer_record["record"] -= xfer
    else:
        xfer = xfer_in(xfer_record["limit"], xfer_record["record"], xfer)
        if not xfer:
            return f"本群转入金币已到达限制：{xfer_record['limit']}"
        if n := STD_GOLD.deal(user.bank, -xfer):
            return f"数量不足。\n——你还有{n}枚标准金币。"
        xfer = int(xfer / group.level)
        GOLD.deal(account.bank, xfer)
        xfer_record["record"] += xfer
    return f"金币转移完成。目标账户实际入账{xfer}(本群汇率：{group.level})"


@plugin.handle({"金币转移"}, {"user_id", "group_id"})
async def _(event: Event):
    args = event.raw_event.args
    if len(args) < 2:
        return
    group_name, xfer = args[:2]
    xfer = to_int(xfer)
    if not xfer:
        return
    group_in = manager.group_library.get(group_name)
    if not group_in:
        return f"没有 {group_name} 的注册信息"
    user = manager.data.user(event.user_id)
    if not (receiver_account_id := user.accounts_map.get(group_in.id)):
        return f"你在{group_in.nickname}没有帐户"
    group_out = manager.data.group(event.group_id or user.connect)
    if not (sender_account_id := user.accounts_map.get(group_out.id)):
        return "你在本群没有帐户"

    sender_bank = manager.data.account_dict[sender_account_id].bank
    receiver_bank = manager.data.account_dict[receiver_account_id].bank
    if xfer < 0:
        sender_bank, receiver_bank = receiver_bank, sender_bank
        group_out, group_in = group_in, group_out
        xfer = -xfer
    ExRate = group_out.level / group_in.level
    if xfer * ExRate < 1:
        return f"转入金币不可小于1枚（汇率：{round(ExRate,2)}）。"
    record_out = group_out.extra.setdefault("xfers", {"record": 0, "limit": 0})
    sender_xfer = xfer_out(record_out["limit"], record_out["record"], xfer)
    if not sender_xfer:
        return f"{group_out.nickname} 转出金币已到达限制：{record_out['limit']}"
    record_in = group_in.extra.setdefault("xfers", {"record": 0, "limit": 0})
    receiver_xfer = xfer_in(record_in["limit"], record_in["record"], int(ExRate * sender_xfer))
    if not receiver_xfer:
        return f"{group_in.nickname} 转入金币已到达限制：{record_in['limit']}"
    sender_xfer = math.ceil(receiver_xfer / ExRate)
    if n := GOLD.deal(sender_bank, -sender_xfer):
        return f"数量不足。\n——你还有{n}枚金币。"
    GOLD.deal(receiver_bank, receiver_xfer)
    record_out["record"] -= sender_xfer
    record_in["record"] += receiver_xfer
    return f"{group_out.nickname}向{group_in.nickname}转移{sender_xfer} 金币\n汇率 {round(ExRate,2)}\n实际到账金额 {receiver_xfer}"


@plugin.handle({"市场注册", "公司注册", "注册公司"}, {"group_id", "to_me", "permission"})
@to_me.decorator
@group_admin.decorator
async def _(event: Event):
    group_id = event.group_id
    group = manager.data.group(group_id)
    stock = group.stock
    if stock and stock.name:
        return f"本群已在市场注册，注册名：{stock.name}"
    stock_name = event.single_arg()
    if check := item_name_rule(stock_name):
        return check
    if manager.group_library.get(stock_name):
        return f"{stock_name} 已被注册"
    wealths = manager.group_wealths(group_id, GOLD.id)
    stock_value = sum(wealths)
    if stock_value < (limit := company_public_gold):
        return f"本群金币（{round(stock_value,2)}）小于{limit}，注册失败。"
    gini = gini_coef(wealths[:-1])
    if gini > revolt_gini:
        return f"本群基尼系数（{round(gini,3)}）过高，注册失败。"
    stock.id = group_id
    stock.name = stock_name
    stock.time = time.time()
    level = group.level = (sum(ra.values()) if (ra := group.extra.get("revolution_achieve")) else 0) + 1
    issuance = 20000 * level
    group.invest[group_id] = issuance - stock.issuance
    stock.issuance = issuance
    stock.fixed = stock.floating = stock.stock_value = stock_value * level
    manager.group_library.set_item(group.id, {stock_name}, group)
    return f"{stock.name}发行成功，发行价格为{format_number(stock.stock_value/ 20000)}金币"


@plugin.handle({"公司重命名"}, {"user_id", "group_id", "to_me", "permission"})
@to_me.decorator
@group_admin.decorator
async def _(event: Event):
    stock_name = event.single_arg()
    group_id = event.group_id
    group = manager.data.group(group_id)
    stock = group.stock
    if not stock.name:
        return "本群未在市场注册，不可重命名。"
    user = manager.data.user(event.user_id)
    if check := item_name_rule(stock_name):
        return check
    if LICENSE.deal(user.bank, -1):
        return f"你未持有【{LICENSE.name}】"
    old_stock_name = stock.name
    stock.name = stock_name
    manager.group_library.set_item(group.id, {stock_name}, group)
    return f"【{old_stock_name}】已重命名为【{stock_name}】"
