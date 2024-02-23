import random
import math
import re
import asyncio
from pathlib import Path
from datetime import datetime
from io import BytesIO
from PIL import ImageColor
from collections.abc import Callable, Coroutine
from .core.clovers import Event, to_me, superuser, group_admin, at
from .core.manager import Manager
from .core.data import Bank, Account
from .core.utils import to_int

from .prop import library as props_library, GOLD, VIP_CARD, LICENSE
from .core.tools import download_url, item_name_rule, gini_coef
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
    prop_name, N, _ = args
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


@plugin.handle({"金币转移"}, {"user_id", "group_id"})
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    group_name, xfer_out, _ = args
    group_in = manager.group_search(group_name)
    if not group_in:
        return f"没有 {group_name} 的注册信息"
    user = manager.locate_user(event.user_id)
    group_out = manager.locate_group(event.group_id or user.connect)

    bank_in = user.connecting(group_in.group_id).bank
    bank_out = user.connecting(group_out.group_id).bank

    if xfer_out < 0:
        bank_out, bank_in = bank_in, bank_out
        group_out, group_in = group_in, group_out
        xfer_out = -xfer_out

    def get_xfer_record(extra: dict) -> dict:
        return extra.setdefault(
            "xfers",
            {
                "record": 0,
                "limit": int((None or company_public_gold) / 20),
            },
        )

    xfer_record_out = get_xfer_record(group_out.extra)
    if xfer_record_out["limit"] == 0:
        xfer_record_out["limit"] = int((None or company_public_gold) / 20)
    limit = xfer_record_out["limit"]
    record = xfer_record_out["record"]

    info = []

    def return_info():
        return "\n".join(info)

    # 计算转出
    if limit <= abs(record - xfer_out):
        info.append(f"{group_out.name} 转出金币已到达限制：{limit}")
        if limit <= record:
            return return_info()
        xfer_out = limit - record
        info.append(f"重新转出：{xfer_out}金币")

    # 计算转入
    ExRate = group_out.level / group_in.level
    xfer_in = int(ExRate * xfer_out)

    xfer_record_in = get_xfer_record(group_in.extra)
    if xfer_record_in["limit"] == 0:
        xfer_record_in["limit"] = int((None or company_public_gold) / 20)
    limit = xfer_record_in["limit"]
    record = xfer_record_in["record"]

    if limit <= record + xfer_in:
        info.append(f"{group_in.name} 转入金币已到达限制：{limit}")
        if limit <= record:
            return return_info()
        xfer_in_OK = limit - record
        xfer_out_OK = math.ceil(xfer_in_OK / ExRate)
        info.append(f"重新转入：{xfer_in_OK} 金币")
    else:
        xfer_in_OK = xfer_in
        xfer_out_OK = xfer_out

    if n := GOLD.deal(bank_out, -xfer_out_OK):
        info.append(f"数量不足。\n——你还有{n}枚金币。")
        return return_info()
    GOLD.deal(bank_in, xfer_in_OK)
    info.append(f"{group_out.name} 向 {group_in.name} 转移{xfer_out_OK}金币")
    info.append(f"汇率 {round(ExRate,2)}\n实际到账金额 {xfer_in_OK}")
    xfer_record_out["record"] -= xfer_out_OK
    xfer_record_in["record"] += xfer_in_OK

    return return_info()


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


@plugin.handle({"我的资产"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    user, group_account = manager.account(event)
    invest = {}
    invest.update(user.bank)
    invest.update(group_account.bank)
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
    command, N, _ = args
    user_id = event.user_id
    group_id = event.group_id
    group = manager.locate_group(group_id)
    if command == "查看":
        bank_data = bank_to_data(group.bank, props_library.search)
        if len(bank_data) < 6:
            info = bank_card(bank_data)
        else:
            info = [prop_card(bank_data)]
        invest_data = bank_to_data(group.bank, manager.stocks_library.search)
        info.append(invest_card(invest_data))
        return manager.info_card(info, user_id)
    sign, name = command[0], command[1:]
    user = manager.locate_user(user_id)
    if item := props_library.search(name):
        bank_in = group.bank
        bank_out = user.locate_bank(group_id, item.domain)
    elif item := manager.stock_search(name):
        bank_in = group.invest
        bank_out = user.connecting(group_id).invest
    else:
        return f"没有名为【{name}】的道具或股票。"

    if sign == "取":
        if not event.permission:
            return f"你的权限不足。"
        N = -1
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
    if stock.name:
        return f"本群已在市场注册，注册名：{stock.name}"
    stock_name = event.single_arg()
    if manager.group_search(stock_name):
        return f"{stock_name} 已被注册"
    if check := item_name_rule(stock_name):
        return check
    stock_value = manager.group_wealths(group_id, GOLD.id)
    if stock_value < (limit := company_public_gold):
        return f"本群金币（{round(stock_value,2)}）小于{limit}，注册失败。"
    gini = gini_coef(group_id)
    if gini > 0.56:
        return f"本群基尼系数（{round(gini,3)}）过高，注册失败。"
    stock.id = group_id
    stock.name = stock_name
    stock.time = datetime.today()
    group.extra.get("revolution", {}).values()
    level = group.level = sum(group.extra.get("revolution", {}).values()) + 1
    if stock.issuance == 0:
        group.invest[group_id] = stock.issuance = 20000 * level
    stock.fixed = stock.floating = stock.stock_value = stock_value * level
    return f"{stock.name}发行成功，发行价格为{round((stock.stock_value/ 20000),2)}金币"


@plugin.handle(r"^.+排行.*", {"user_id", "group_id"})
async def _(event: Event):
    cmd_match = re.search(r"(.+)排行(.*)", event.raw_event.raw_command.strip())
    title = cmd_match.group(1)
    group_name = cmd_match.group(2) or event.group_id or manager.locate_user(event.user_id).connect
    group = manager.group_search(group_name)
    group_id = group.group_id if group else None
    if title == "路灯挂件":
        data = {}
        for group in manager.data.group_dict.values():
            for k, v in group.extra.setdefault("revolution_achieve"):
                data[k] = data.get(k, 0) + v
        ranklist = list(data.items())
        ranklist.sort(key=lambda x: x[1], reverse=True)
    else:
        if title.endswith("总"):
            namelist = manager.namelist()
            key = manager.rankkey(title[:-1])
        else:
            if not group_id:
                return
            namelist = manager.namelist(group_name)
            key = manager.rankkey(title)
            prop = props_library.search(title)
            if not key:
                if not prop:
                    return
                key = lambda user_id: manager.locate_user(user_id).locate_bank(group_id, prop.domain).get(prop.id, 0)

        ranklist = manager.ranklist(namelist, key)

    if not ranklist:
        return f"无数据，无法进行{title}排行"
    nickname_data = []
    rank_data = []
    task_list = []
    for user_id, v in ranklist[:20]:
        user = manager.locate_user(user_id)
        nickname_data.append(user.nickname(group_id))
        rank_data.append(v)
        task_list.append(download_url(user.avatar_url))
    avatar_data = await asyncio.gather(*task_list)
    return manager.info_card([draw_rank(list(zip(nickname_data, rank_data, avatar_data)))], event.user_id, "NONE")


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
    name, N, _ = args
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
