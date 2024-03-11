import random
from pathlib import Path
from datetime import datetime
from PIL import ImageColor
from clovers_apscheduler import scheduler
from clovers_leafgame_core.clovers import Event, to_me, superuser, at
from clovers_utils.tools import download_url, format_number
from .item import (
    GOLD,
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
from .leafgame import *

sign_gold = config.sign_gold
clovers_marking = config.clovers_marking
revolution_marking = config.revolution_marking
debug_marking = config.debug_marking


invest_data = lambda bank: [(stock, n) for group_id, n in bank.items() if n != 0 and (stock := manager.group_library[group_id].stock)]
props_data = lambda bank: [(prop, n) for prop_id, n in bank.items() if n != 0 and (prop := manager.props_library.get(prop_id))]


@plugin.handle({"设置背景"}, {"user_id", "to_me", "image_list"})
@to_me.decorator
async def _(event: Event):
    user_id = event.user_id
    user = manager.data.user(user_id)
    if LICENSE.deal(user.bank, -1):
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
    today = datetime.today()
    if account.sign_in and (today - account.sign_in).days == 0:
        return "你已经签过到了哦"
    N = random.randint(*sign_gold)
    account.sign_in = today
    GOLD.deal(account.bank, N)
    return random.choice(["祝你好运~", "可别花光了哦~"]) + f"\n你获得了 {N} 金币"


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
