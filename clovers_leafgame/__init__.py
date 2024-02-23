import random
import math
import re
import asyncio
import time
from pathlib import Path
from datetime import datetime
from PIL import ImageColor
from .core.clovers import Event, to_me, superuser, group_admin, at
from .core.utils import item_name_rule, to_int

from .prop import library as props_library, GOLD, STD_GOLD, VIP_CARD, LICENSE
from .core.utils import download_url, gini_coef
from .output import (
    bank_to_data,
    bank_card,
    prop_card,
    invest_card,
    draw_rank,
)
from .main import plugin, config, manager

sign_gold = config.sign_gold
revolt_gold = config.revolt_gold
revolt_gini = config.revolt_gini
company_public_gold = config.company_public_gold
gacha_gold = config.gacha_gold


@plugin.handle({"设置背景"}, {"user_id", "to_me", "image_list"})
@to_me.wrapper
async def _(event: Event):
    user_id = event.user_id
    user = manager.locate_user(user_id)
    print(user.bank, LICENSE.id)
    if user.bank.get(LICENSE.id, 0) < 1:
        return f"你的【{LICENSE.name}】已失效"
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
@to_me.wrapper
async def _(event: Event):
    Path.unlink(manager.BG_PATH / f"{event.user_id}.png", True)
    return "背景图片删除成功！"


@plugin.handle({"金币签到", "轮盘签到"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event):
    user, account = manager.account(event)
    user.avatar_url = event.avatar
    delta_days = (datetime.today() - account.sign_date).days
    if delta_days == 0:
        return "你已经签过到了哦"
    N = random.randint(*sign_gold) * delta_days
    GOLD.deal(account.bank, N)
    return random.choice(["祝你好运~", "可别花光了哦~"]) + f"\n你获得了 {N} 金币"


@plugin.handle({"重置签到", "领取金币"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event):
    user, account = manager.account(event)
    user.avatar_url = event.avatar
    if account.revolution:
        return "你没有待领取的金币"
    N = random.randint(*revolt_gold)
    GOLD.deal(account.bank, N)
    account.revolution = True
    return f"这是你重置后获得的金币！你获得了 {N} 金币"


@plugin.handle({"发红包", "赠送金币"}, {"user_id", "group_id", "at", "permission"})
@at.wrapper
async def _(event: Event):
    group_id = event.group_id
    N = event.args_to_int() or random.randint(*sign_gold)
    user_out = manager.locate_user(event.user_id)
    user_in = manager.locate_user(event.at[0])
    if N < 0:
        if event.permission < 2:
            return "你发了负数的红包，请不要这样做。"
        user_out, user_in = user_in, user_out
        N = -N
        sender = "对方"
    else:
        sender = "你"
    if VIP_CARD.user_bank(user_out, group_id).get(VIP_CARD.id, 0) > 0:
        tax = 0
        tip = f"『{VIP_CARD.name}』免手续费"
    else:
        tax = int(N * 0.02)
        tip = f"扣除2%手续费：{tax}，实际到账金额{N - tax}"

    if n := GOLD.deal_with(user_out, group_id, -N):
        return f"数量不足。\n——{sender}还有{n}枚金币。"
    GOLD.deal_with(user_in, group_id, -N)
    GOLD.deal(manager.locate_group(group_id).bank, tax)
    return f"{user_out.nickname(group_id)} 向 {user_in.nickname(group_id)} 赠送{N}枚金币\n{tip}"


@plugin.handle({"送道具", "赠送道具"}, {"user_id", "group_id", "at", "permission"})
@at.wrapper
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    prop_name, N = args[:2]
    prop = props_library.search(prop_name)
    if not prop:
        return f"没有【{prop_name}】这种道具。"
    group_id = event.group_id
    N = event.args_to_int() or random.randint(*sign_gold)
    user_out = manager.locate_user(event.user_id)
    user_in = manager.locate_user(event.at[0])
    if N < 0:
        if event.permission < 2:
            return "你发了负数的红包，请不要这样做。"
        user_out, user_in = user_in, user_out
        N = -N
        sender = "对方"
    else:
        sender = "你"

    if prop is GOLD:
        tax = int(N * 0.1)
        tip = f"消耗10%道具转换成本：{tax}，实际到账金额{N - tax}"
    else:
        tax, tip = 0, ""

    if n := prop.deal_with(user_out, group_id, -N):
        return f"数量不足。\n——{sender}还有{n}个{prop.name}。"
    prop.deal_with(user_in, group_id, N - tax)
    prop.deal(manager.locate_group(group_id).bank, tax)

    return f"{user_out.nickname(group_id)} 向 {user_in.nickname(group_id)} 赠送{N}个{prop.name}\n{tip}"


@plugin.handle({"金币转移"}, {"user_id"})
async def _(event: Event):
    xfer = event.args_to_int()
    user = manager.locate_user(event.user_id)
    user_bank = user.bank
    group = manager.locate_group(event.group_id or user.connect)
    account_bank = user.connecting(group.group_id).bank
    level = group.level
    if xfer < 0:
        xfer = -xfer
        xfer = group.xfer_out(xfer)
        if not xfer:
            return f"{group.name} 转出金币已到达限制：{group.xfer_record['record']}"
        if n := GOLD.deal(account_bank, -xfer):
            return f"数量不足。\n——你在{group.name}还有{n}枚金币。"
        STD_GOLD.deal(user_bank, int(xfer * level))
    else:
        xfer = group.xfer_in(xfer)
        if not xfer:
            return f"{group.name} 转入金币已到达限制：{group.xfer_record['record']}"
        if n := STD_GOLD.deal(user_bank, -math.ceil(xfer * level)):
            return f"数量不足。\n——你在还有{n}枚标准金币(本群汇率：{level})。"
        GOLD.deal(account_bank, xfer)
    return f"金币转移完成。目标账户实际入账{xfer}"


@plugin.handle({"金币转移"}, {"user_id", "group_id"})
async def _(event: Event):
    args = event.raw_event.args
    if len(args) < 2:
        return
    group_name, xfer_out = args[:2]
    xfer_out = to_int(xfer_out)
    if not xfer_out:
        return
    user = manager.locate_user(event.user_id)
    group_in = manager.group_search(args[0])
    if not group_in:
        return f"没有 {group_name} 的注册信息"
    bank_in = user.connecting(group_in.group_id).bank
    group_out = manager.locate_group(event.group_id or user.connect)
    bank_out = user.connecting(group_out.group_id).bank
    if xfer_out < 0:
        bank_out, bank_in = bank_in, bank_out
        group_out, group_in = group_in, group_out
        xfer_out = -xfer_out

    xfer_out = group_out.xfer_out(xfer_out)
    if not xfer_out:
        return f"{group_out.name} 转出金币已到达限制：{group_out.xfer_record['record']}"
    ExRate = group_out.level / group_in.level
    xfer_in = group_in.xfer_in(int(ExRate * xfer_out))
    if not xfer_in:
        return f"{group_in.name} 转入金币已到达限制：{group_in.xfer_record['record']}"
    xfer_out = math.ceil(xfer_in / ExRate)
    if n := GOLD.deal(bank_out, -xfer_out):
        return f"数量不足。\n——你还有{n}枚金币。"
    GOLD.deal(bank_in, xfer_in)
    group_in.xfer_record["record"] += xfer_in
    group_out.xfer_record["record"] -= xfer_out
    return f"{group_out.name}向{group_in.name}转移{xfer_out} 金币\n汇率 {round(ExRate,2)}\n实际到账金额 {xfer_in}"


@plugin.handle({"我的金币"}, {"user_id", "group_id"})
async def _(event: Event):
    user = manager.locate_user(event.user_id)
    code = GOLD.id
    if event.is_private():
        info = []
        for group_id, accounts in user.accounts.items():
            group = manager.group_search(group_id)
            if not group:
                group_name = "账户已失效"
            else:
                group_name = group.name
            if N := accounts.bank.get(code):
                info.append(f"【{group_name}】金币{N}枚")
        if info:
            return "你的账户:\n" + "\n".join(info)
    return f"你还有 {user.connecting(event.group_id).bank.get(code,0)} 枚金币"


@plugin.handle({"我的道具"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    user, group_account = manager.account(event)
    props = {}
    props.update(user.bank)
    props.update(group_account.bank)
    if not props:
        return "您的仓库空空如也。"
    flag = len(props) < 10 or event.single_arg() in {"信息", "介绍", "详情"}
    data = bank_to_data(props, props_library.search)
    if flag:
        info = bank_card(data)
    else:
        info = [prop_card(data)]
    return manager.info_card(info, event.user_id)


@plugin.handle({"我的资产"}, {"user_id"})
async def _(event: Event):
    invest = user = manager.locate_user(event.user_id).invest
    if not invest:
        return "您的资产是空的。"
    return manager.info_card(
        [invest_card(bank_to_data(invest, manager.stocks_library.search))],
        event.user_id,
    )


@plugin.handle({"群金库"}, {"user_id", "group_id", "permission"})
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    command, Nc = args[:2]
    user_id = event.user_id
    group_id = event.group_id
    group = manager.locate_group(group_id)
    if command == "查看":
        bank_data = bank_to_data(group.bank, props_library.search)
        if len(bank_data) < 6:
            info = bank_card(bank_data)
        else:
            info = [prop_card(bank_data, "群金库")]
        invest_data = bank_to_data(group.bank, manager.stocks_library.search)
        info.append(invest_card(invest_data, "群投资"))
        return manager.info_card(info, user_id)
    sign, name = command[0], command[1:]
    user = manager.locate_user(user_id)
    if item := props_library.search(name):
        bank_in = group.bank
        bank_out = item.user_bank(user, group_id)
    elif item := manager.stocks_library.search(name):
        bank_in = group.invest
        bank_out = user.connecting(group_id).invest
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
@at.wrapper
@group_admin.wrapper
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


@plugin.handle({"获取金币"}, {"user_id", "group_id", "permission"})
@superuser.wrapper
async def _(event: Event):
    N = event.args_to_int()
    user = manager.locate_user(event.user_id)
    if n := GOLD.deal_with(user, event.group_id, N):
        return f"获取金币失败，你的金币（{n}）数量不足。"
    return f"你获得了 {N} 金币"


@plugin.handle({"获取道具"}, {"user_id", "group_id", "nickname", "permission"})
@superuser.wrapper
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    name, N = args[:2]
    prop = props_library.search(name)
    if not prop:
        return f"没有【{name}】这种道具。"
    user = manager.locate_user(event.user_id)
    if n := prop.deal_with(user, event.group_id, N):
        return f"获取道具失败，你的【{prop.name}】（{n}））数量不足。"
    return f"你获得了{N}个【{prop.name}】！"


@plugin.task
async def _():
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
