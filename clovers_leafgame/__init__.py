import random
import math
import time
from pathlib import Path
from datetime import datetime
from PIL import ImageColor
from clovers_apscheduler import scheduler
from clovers_leafgame_core.clovers import Event, to_me, superuser, group_admin, at
from clovers_utils.tools import item_name_rule, to_int, download_url, gini_coef, format_number
from .item import (
    Prop,
    GOLD,
    STD_GOLD,
    LICENSE,
    CLOVERS_MARKING,
    REVOLUTION_MARKING,
    DEBUG_MARKING,
)
from .output import (
    bank_card,
    prop_card,
    invest_card,
    avatar_card,
    account_card,
)
from .main import plugin, config, manager

sign_gold = config.sign_gold
revolt_gold = config.revolt_gold
revolt_gini = config.revolt_gini
company_public_gold = config.company_public_gold

clovers_marking = config.clovers_marking
revolution_marking = config.revolution_marking
debug_marking = config.debug_marking


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


invest_data = lambda bank: [(stock, n) for group_id, n in bank.items() if n != 0 and (stock := manager.group_library[group_id].stock)]
props_data = lambda bank: [(prop, n) for prop_id, n in bank.items() if n != 0 and (prop := manager.props_library.get(prop_id))]


@plugin.handle({"设置背景"}, {"user_id", "to_me", "image_list"})
@to_me.decorator
async def _(event: Event):
    user_id = event.user_id
    user = manager.data.user(user_id)
    if user.bank.get(LICENSE, 0) < 1:
        return f"你未持有【{LICENSE.name}】"
    log = []
    BG_type = event.single_arg()
    if BG_type:
        if BG_type in {"高斯模糊", "模糊"}:
            user.extra["BG_type"] = "GAUSS"
            log.append("背景蒙版类型设置为：高斯模糊")
        elif BG_type in {"无", "透明"}:
            log.append("背景蒙版类型设置为：透明")
            user.extra["BG_type"] = "NONE"
        elif BG_type.startswith("#"):
            log.append(f"背景蒙版类型设置为：{BG_type}")
            try:
                ImageColor.getcolor(BG_type, "RGB")
                user.extra["BG_type"] = BG_type
            except ValueError:
                log.append("设置失败")

    if url_list := event.raw_event.kwargs["image_list"]:
        image = await download_url(url_list[0])
        if not image:
            log.append("图片下载失败")
        else:
            with open(manager.BG_PATH / f"{user_id}.png", "wb") as f:
                f.write(image)
            log.append("图片下载成功")
    if log:
        return "\n".join(log)


@plugin.handle({"删除背景"}, {"user_id", "to_me"})
@to_me.decorator
async def _(event: Event):
    Path.unlink(manager.BG_PATH / f"{event.user_id}.png", True)
    return "背景图片删除成功！"


@plugin.handle({"金币签到", "轮盘签到"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event):
    user, account = manager.account(event)
    user.avatar_url = event.avatar
    delta_days = (datetime.today() - account.sign_in).days
    if delta_days == 0:
        return "你已经签过到了哦"
    N = random.randint(*sign_gold) * delta_days
    GOLD.deal(account.bank, N)
    return random.choice(["祝你好运~", "可别花光了哦~"]) + f"\n你获得了 {N} 金币"


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


@plugin.handle({"发红包"}, {"user_id", "group_id", "at", "permission"})
@at.decorator
async def _(event: Event):
    unsettled = event.args_to_int()
    sender_id = event.user_id
    receiver_id = event.at[0]
    if unsettled < 0:
        if event.permission < 2:
            return "你输入了负数，请不要这样做。"
        sender_id, receiver_id = receiver_id, sender_id
        unsettled = -unsettled
    return manager.transfer(GOLD, unsettled, sender_id, receiver_id, event.group_id)


@plugin.handle({"送道具"}, {"user_id", "group_id", "at", "permission"})
@at.decorator
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    prop_name, unsettled = args[:2]
    prop = manager.props_library.get(prop_name)
    if not prop:
        return f"没有【{prop_name}】这种道具。"
    if unsettled < 0:
        if event.permission < 2:
            return "你输入了负数，请不要这样做。"
        sender_id, receiver_id = receiver_id, sender_id
        unsettled = -unsettled
    return manager.transfer(prop, unsettled, sender_id, receiver_id, event.group_id)


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


@plugin.handle({"查询我的"}, {"user_id", "group_id"})
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    prop = manager.props_library.get(args[0])
    if not prop:
        return
    user_id = event.user_id
    user = manager.data.user(user_id)
    if prop.domain != 1:
        return f"你还有 {user.bank.get(prop.id,0)} 个{prop.name}"
    if event.is_private():
        info = []
        for group_id, account_id in user.accounts_map.items():
            account = manager.data.account_dict[account_id]
            info.append(f"【{manager.data.group(group_id).nickname}】{prop.name} {account.bank.get(prop.id,0)}个")
        if info:
            return "你的账户:\n" + "\n".join(info)
        else:
            return "你的账户是空的"
    group_id = event.group_id
    account_id = user.accounts_map.get(group_id)
    if account_id:
        account = manager.data.account_dict[account_id]
    else:
        account = manager.new_account(user_id, group_id)
    return f"你还有 {account.bank.get(prop.id,0)} 个{prop.name}"


@plugin.handle({"我的信息", "我的资料"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    user, account = manager.account(event)
    info = []
    lines = []
    if DEBUG_MARKING.N(user, account):
        lines.append(debug_marking)
    if CLOVERS_MARKING.N(user, account):
        lines.append(clovers_marking)
    if REVOLUTION_MARKING.N(user, account):
        lines.append(revolution_marking)

    info.append(
        avatar_card(
            await download_url(user.avatar_url),
            account.name or user.name or user.id,
            lines,
        )
    )
    lines = []
    i = 0
    for marking_prop in manager.marking_library.values():
        if count := marking_prop.N(user, account):
            count = min(count, 99)
            lines.append(f"[color][{marking_prop.color}]Lv.{count}{'  'if count < 10 else ' '}{marking_prop.tip}")
            i += 1
            if i == 3:
                break

    lines += ["" for _ in range(3 - len(lines))]
    lines.append(f"金币 {format_number(account.bank.get(GOLD.id, 0))}")
    lines.append(f"股票 {format_number(manager.stock_value(user.invest))}")
    delta_days = (datetime.today() - account.sign_in).days

    if delta_days == 0:
        lines.append("[color][green]今日已签到")
    else:
        lines.append(f"[color][red]连续{delta_days}天 未签到")

    dist = [
        (n, manager.data.group(group_id).name)
        for group_id, account_id in user.accounts_map.items()
        if (n := manager.data.account_dict[account_id].bank.get(GOLD.id, 0)) > 0
    ]
    info.append(account_card(dist or [(1, "None")], "\n".join(lines)))
    data = invest_data(user.invest)
    if data:
        info.append(invest_card(data, "股票信息"))
    return manager.info_card(info, event.user_id)


@plugin.handle({"我的道具"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    user, group_account = manager.account(event)
    props = {}
    props.update(user.bank)
    props.update(group_account.bank)
    if not props:
        return "您的仓库空空如也。"

    data = props_data(props)
    if len(data) < 10 or event.single_arg() in {"信息", "介绍", "详情"}:
        info = bank_card(data)
    else:
        info = [prop_card(data)]
    return manager.info_card(info, event.user_id)


@plugin.handle({"群金库"}, {"user_id", "group_id", "permission"})
async def _(event: Event):
    if event.is_private() or not (args := event.args_parse()):
        return
    command, N = args[:2]
    user_id = event.user_id
    group_id = event.group_id
    group = manager.data.group(group_id)
    if command == "查看":
        data = props_data(group.bank)
        if len(data) < 6:
            info = bank_card(data)
        else:
            info = [prop_card(data, "群金库")]
        data = invest_data(group.invest)
        if data:
            info.append(invest_card(data, "群投资"))
        return manager.info_card(info, user_id) if info else "群金库是空的"
    sign, name = command[0], command[1:]
    user, account = manager.locate_account(user_id, group_id)
    if item := manager.props_library.get(name):
        bank_in = group.bank
        bank_out = item.locate_bank(user, account)
    elif (group := manager.group_library.get(name)) and (item := group.stock):
        bank_in = group.invest
        bank_out = user.invest
    else:
        return f"没有名为【{name}】的道具或股票。"

    if sign == "取":
        if not event.permission:
            return f"你的权限不足。"
        N = -N
        bank_out, bank_in = bank_in, bank_out
        sender = "群金库"
    elif sign == "存":
        sender = "你"
    else:
        return
    if n := item.deal(bank_out, -N):
        return f"{command}失败，{sender}还有{n}个{item.name}。"
    item.deal(bank_in, N)
    return f"你在群金库{sign}了{N}个{item.name}"


@plugin.handle({"市场注册", "公司注册", "注册公司"}, {"to_me", "permission"})
@at.decorator
@group_admin.decorator
async def _(event: Event):
    group_id = event.group_id
    group = manager.locate_group(group_id)
    stock = group.stock
    if stock and stock.name:
        return f"本群已在市场注册，注册名：{stock.name}"
    stock_name = event.single_arg()
    if check := item_name_rule(stock_name):
        return check
    if manager.group_search(stock_name):
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
    level = group.level = sum(group.extra.setdefault("revolution_achieve", {}).values()) + 1
    issuance = 20000 * level
    group.invest[group_id] = stock.issuance - issuance
    stock.issuance = issuance
    stock.fixed = stock.floating = stock.stock_value = stock_value * level
    return f"{stock.name}发行成功，发行价格为{round((stock.stock_value/ 20000),2)}金币"


# 超管指令


@plugin.handle({"获取"}, {"user_id", "group_id", "nickname", "permission"})
@superuser.decorator
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    name, N = args[:2]
    prop = manager.props_library.get(name)
    if not prop:
        return f"没有【{name}】这种道具。"
    if n := prop.deal(prop.locate_bank(*manager.account(event)), N):
        return f"获取失败，你的【{prop.name}】（{n}））数量不足。"
    return f"你获得了{N}个【{prop.name}】！"


@plugin.handle({"保存游戏"}, {"permission"})
@superuser.decorator
@scheduler.scheduled_job("cron", minute="*/10", misfire_grace_time=120)
async def _():
    manager.save()
    print("游戏数据已保存！")


__plugin__ = plugin

"""
恶魔轮盘：

一把只有一发空仓的左轮枪。你可以对自己开一枪，如果你足够幸运躲过一劫，那么你的名下所有账户的金币与股票净值都将翻10倍。
如果你不幸中弹,你将会在这个世界上消失。

绯红迷雾之书：

把你的个人数据回溯到到任意时间节点。
可回溯的时间节点有多少取决于服务器备份设置
    --机器人bug研究中心

手中的左轮没有消失，你的眼前出现了一张纸条。
为了庆祝你活了下来,我们还要送你一份礼物。
你手中的左轮已经重新装好了子弹。
你可以把它扔在仓库里。
但是如果你想继续开枪的话，那就来吧。
                            ——小月儿
*你获得了 【恶魔轮盘】*1

"""
