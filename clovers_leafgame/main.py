import random
import math
import re
import asyncio
from pathlib import Path
from datetime import datetime
from clovers_core.plugin import Result

from .core.clovers import Event
from .account import Manager
from .core.data import Bank, Account
from .core.utils import to_int

from .config import config, BG_PATH
from .clover import plugin, Check
from .library import prop_search, GOLD, VIP_CARD, AIR_PACK, LICENSE, gacha
from .utils.linecard import info_splicing
from .utils.tools import download_url, format_number, item_name_rule, gini_coef
from .output import (
    bank_to_data,
    bank_card,
    prop_card,
    invest_card,
    gacha_report_card,
    draw_rank,
)


sign_gold = config.sign_gold
revolt_gold = config.revolt_gold
company_public_gold = config.company_public_gold
gacha_gold = config.gacha_gold

manager = Manager(Path(config.main_path) / "russian_data.json")

to_me = Check(to_me=True)
superuser = Check(superuser=True)
group_admin = Check(group_admin=True)
at = Check(at=True)


def info_card(info, user_id, BG_type=None):
    extra = manager.locate_user(user_id).extra
    BG_type = BG_type or extra.get("BG_type", "#FFFFFF99")
    bg_path = BG_PATH / f"{user_id}.png"
    if not bg_path.exists():
        bg_path = BG_PATH / "default.png"
    try:
        return info_splicing(info, bg_path, spacing=10, BG_type=BG_type)
    except:
        if "BG_type" in extra:
            del extra["BG_type"]


@plugin.handle({"金币签到", "轮盘签到"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event) -> Result:
    user, account = manager.account(event)
    user.avatar_url = event.avatar
    delta_days = (datetime.today() - account.sign_date).days
    if delta_days == 0:
        return "你已经签过到了哦"
    N = random.randint(*sign_gold) * delta_days
    GOLD.deal(account.bank, N)
    return random.choice(["祝你好运~", "可别花光了哦~"]) + f"\n你获得了 {N} 金币"


@plugin.handle({"重置签到", "领取金币"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event) -> Result:
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
async def _(event: Event) -> Result:
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
    if user_out.locate_bank(group_id, VIP_CARD.domain).get(VIP_CARD.id, 0) > 0:
        tax = 0
        tip = f"『{VIP_CARD.name}』免手续费"
    else:
        tax = int(N * 0.02)
        tip = f"扣除2%手续费：{tax}，实际到账金额{N - tax}"

    if n := user_out.deal(group_id, GOLD, -N):
        return f"数量不足。\n——{sender}还有{n}枚金币。"

    user_in.deal(group_id, GOLD, N - tax)
    GOLD.deal(manager.locate_group(group_id).bank, tax)
    return f"{user_out.nickname(group_id)} 向 {user_in.nickname(group_id)} 赠送{N}枚金币\n{tip}"


@plugin.handle({"送道具", "赠送道具"}, {"user_id", "group_id", "at", "permission"})
@at.wrapper
async def _(event: Event) -> Result:
    if not (args := event.args_parse()):
        return
    prop_name, N, _ = args
    prop = prop_search(prop_name)
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

    if n := user_out.deal(group_id, prop, -N):
        return f"数量不足。\n——{sender}还有{n}个{prop.name}。"
    user_in.deal(group_id, prop, N - tax)
    prop.deal(manager.locate_group(group_id).bank, tax)
    return f"{user_out.nickname(group_id)} 向 {user_in.nickname(group_id)} 赠送{N}个{prop.name}\n{tip}"


@plugin.handle({"金币转移"}, {"user_id", "group_id"})
async def _(event: Event) -> Result:
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
async def _(event: Event) -> Result:
    user = manager.locate_user(event.user_id)
    code = GOLD.id
    if event.is_private():
        info = []
        for group_id, accounts in user.accounts.items():
            group = manager.group_search(group_id, False)
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
async def _(event: Event) -> Result:
    user, group_account = manager.account(event)
    props = {}
    props.update(user.bank)
    props.update(group_account.bank)
    if not props:
        return "您的仓库空空如也。"
    flag = len(props) < 10 or event.single_arg() in {"信息", "介绍", "详情"}
    data = bank_to_data(props, prop_search)
    if flag:
        info = bank_card(data)
    else:
        info = [prop_card(data)]
    return info_card(info, event.user_id)


@plugin.handle({"我的资产"}, {"user_id", "group_id", "nickname"})
async def _(event: Event) -> Result:
    user, group_account = manager.account(event)
    invest = {}
    invest.update(user.bank)
    invest.update(group_account.bank)
    if not invest:
        return "您的资产是空的。"
    return info_card(
        [invest_card(bank_to_data(invest, manager.stock_search))],
        event.user_id,
    )


@plugin.handle({"群金库"}, {"user_id", "group_id", "permission"})
async def _(event: Event) -> Result:
    if not (args := event.args_parse()):
        return
    command, N, _ = args
    user_id = event.user_id
    group_id = event.group_id
    group = manager.locate_group(group_id)
    if command == "查看":
        bank_data = bank_to_data(group.bank, prop_search)
        if len(bank_data) < 6:
            info = bank_card(bank_data)
        else:
            info = [prop_card(bank_data)]
        invest_data = bank_to_data(group.bank, manager.stock_search)
        info.append(invest_card(invest_data))
        return info_card(info, user_id)
    sign, name = command[0], command[1:]
    user = manager.locate_user(user_id)
    if item := prop_search(name):
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


@plugin.handle(r"^.+连抽?卡?|单抽", {"user_id", "group_id", "nickname", "to_me"})
@to_me.wrapper
async def _(event: Event) -> Result:
    N = re.search(r"^(.*)连抽?卡?$", event.raw_event.raw_command)
    if not N:
        return
    N = to_int(N.group(1))
    if not N:
        return
    N = 200 if N > 200 else 1 if N < 1 else N
    gold = N * gacha_gold
    user_id = event.user_id
    user = manager.locate_user(user_id)
    group_id = event.group_id or user.connect
    if n := user.deal(group_id, GOLD, -gold):
        return f"{N}连抽卡需要{gold}金币，你的金币：{n}。"
    bank: Bank = {}
    for _ in range(N):
        prop_code = gacha()
        bank[prop_code] = bank.get(prop_code, 0) + 1
    data = bank_to_data(bank, prop_search)
    prop_data = {0: [], 1: [], 2: []}
    report_data = {"prop_star": 0, "prop_n": 0, "air_star": 0, "air_n": 0}
    for seg in data:
        prop, n = seg
        prop_data[prop.domain].append(seg)
        rare = prop.rare
        if prop.domain == 0:
            report_data["air_star"] += rare * n
            report_data["air_n"] += n
        else:
            user.deal(group_id, prop, n)
            report_data["prop_star"] += rare * n
            report_data["prop_n"] += n
    info = []
    info.append(gacha_report_card(user.nickname(group_id), **report_data))
    if report_data["prop_n"] == 0:
        user.deal(group_id, GOLD, gold)
        user.deal(group_id, AIR_PACK, 1)
        info.append(prop_card([(AIR_PACK, 1)], f"本次抽卡已免费（{gold}金币）"))
    if data := prop_data[2]:
        info.append(prop_card(data, "全局道具"))
    if data := prop_data[1]:
        info.append(prop_card(data, "群内道具"))
    if data := prop_data[0]:
        info.append(prop_card(data, "未获取"))
    return info_card(info, user_id)


@plugin.handle({"市场注册", "公司注册", "注册公司"}, {"to_me", "permission"})
@at.wrapper
@group_admin.wrapper
async def _(event: Event) -> Result:
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
            prop = prop_search(title)
            if not key:
                prop = prop_search(title)
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
    return info_card([draw_rank(list(zip(nickname_data, rank_data, avatar_data)))], event.user_id, "NONE")


@plugin.handle({"使用道具"}, {"user_id", "group_id"})
async def _(event: Event) -> Result:
    if not (args := event.args_parse()):
        return
    prop_name, count, _ = event.args_parse()
    prop = prop_search(prop_name)
    if not prop:
        return f"没有{prop_name}这种道具"
    return prop.use()


# 超管指令


@plugin.handle({"获取金币"}, {"user_id", "group_id", "permission"})
@superuser.wrapper
async def _(event: Event) -> Result:
    N = event.args_to_int()
    user = manager.locate_user(event.user_id)
    if n := user.deal(event.group_id, GOLD, N):
        return f"获取金币失败，你的金币（{n}）数量不足。"
    return f"你获得了 {N} 金币"


@plugin.handle({"获取道具"}, {"user_id", "group_id", "nickname", "permission"})
@superuser.wrapper
async def _(event: Event) -> Result:
    if not (args := event.args_parse()):
        return
    name, N, _ = args
    prop = prop_search(name)
    if not prop:
        return f"没有【{name}】这种道具。"
    user = manager.locate_user(event.user_id)
    if n := user.deal(event.group_id, prop, N):
        return f"获取道具失败，你的【{prop.name}】（{n}））数量不足。"
    return f"你获得了{N}个【{prop.name}】！"


@plugin.task
async def _():
    print("游戏数据已保存！")
