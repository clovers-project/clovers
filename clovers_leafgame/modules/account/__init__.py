import random
from pathlib import Path
from datetime import datetime
from PIL import ImageColor
from collections import Counter
from clovers.utils.tools import download_url, format_number
from clovers_leafgame.core.clovers import Event, Check
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import (
    GOLD,
    STD_GOLD,
    LICENSE,
    CLOVERS_MARKING,
    REVOLUTION_MARKING,
    DEBUG_MARKING,
)
from clovers_leafgame.output import (
    text_to_image,
    endline,
    candlestick,
    bank_card,
    prop_card,
    invest_card,
    avatar_card,
    dist_card,
)
from clovers.core.config import config as clovers_config
from .config import Config


config_key = __package__
config_data = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config_data.dict()

sign_gold = config_data.sign_gold
clovers_marking = config_data.clovers_marking
revolution_marking = config_data.revolution_marking
debug_marking = config_data.debug_marking


@plugin.handle({"设置背景"}, {"user_id", "to_me", "image_list"})
@Check().to_me().check
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
        elif BG_type in {"无", "透明"}:
            user.extra["BG_type"] = "NONE"
        elif BG_type == "默认":
            if "BG_type" in user.extra:
                del user.extra["BG_type"]
        else:
            try:
                ImageColor.getcolor(BG_type, "RGB")
                user.extra["BG_type"] = BG_type
            except ValueError:
                BG_type = "ValueError"
                pass
        log.append(f"背景蒙版类型设置为：{BG_type}")

    if url_list := event.image_list:
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
@Check().to_me().check
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
    n = random.randint(*sign_gold)
    account.sign_in = today
    GOLD.deal(account.bank, n)
    return random.choice(["祝你好运~", "可别花光了哦~"]) + f"\n你获得了 {n} 金币"


@plugin.handle({"发红包"}, {"user_id", "group_id", "at", "permission"})
@Check().at().check
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
@Check().at().check
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    prop_name, unsettled = args[:2]
    prop = manager.props_library.get(prop_name)
    if not prop:
        return f"没有【{prop_name}】这种道具。"
    sender_id = event.user_id
    receiver_id = event.at[0]
    if unsettled < 0:
        if event.permission < 2:
            return "你输入了负数，请不要这样做。"
        sender_id, receiver_id = receiver_id, sender_id
        unsettled = -unsettled
    return manager.transfer(prop, unsettled, sender_id, receiver_id, event.group_id)


@plugin.handle(r"(.+)查询$", {"user_id", "group_id"})
async def _(event: Event):
    prop = manager.props_library.get(event.args[0])
    if not prop:
        return
    user_id = event.user_id
    user = manager.data.user(user_id)
    if prop.domain != 1:
        return f"你还有 {user.bank[prop.id]} 个{prop.name}"
    if event.is_private():
        info = []
        for group_id, account_id in user.accounts_map.items():
            account = manager.data.account_dict[account_id]
            info.append(f"【{manager.data.group(group_id).nickname}】{prop.name} {account.bank[prop.id]}个")
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
    return f"你还有 {account.bank[prop.id]} 个{prop.name}"


@plugin.handle({"我的信息", "我的资料卡"}, {"user_id", "group_id", "nickname"})
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
    for marking_prop in manager.marking_library.values():
        if count := marking_prop.N(user, account):
            lines.append(f"[color][{marking_prop.color}]Lv.{min(count, 99)}[nowrap][passport]\n[pixel][160]{marking_prop.tip}")
    if lines:
        info.append(text_to_image("\n".join(lines)))
    lines = []
    sum_std_n = user.bank[STD_GOLD.id]
    dist: list[tuple[int, str]] = [(sum_std_n, "个人账户")]
    for group_id, account_id in user.accounts_map.items():
        group = manager.data.group(group_id)
        std_n = manager.data.account_dict[account_id].bank[GOLD.id] * group.level
        if std_n > 0:
            dist.append((std_n, group.nickname))
        sum_std_n += std_n
    lines.append(f"[color][#FFCC33]金币 {format_number(sum_std_n)}")
    lines.append(f"[color][#0066CC]股票 {format_number(manager.stock_value(user.invest))}")
    info.append(text_to_image("\n".join(lines), 40, canvas=dist_card(dist)))
    data = manager.invest_data(user.invest)
    if data:
        info.append(invest_card(data, "股票信息"))
    lines = []
    if account.sign_in is None:
        delta_days = 1
    else:
        delta_days = (datetime.today() - account.sign_in).days
    if delta_days == 0:
        lines.append("[color][green]本群今日已签到")
    else:
        lines.append(f"[color][red]本群连续{delta_days}天 未签到")
    lines += user.message
    info.append(text_to_image("\n".join(lines) + endline("Message"), 30, autowrap=True))
    user.message.clear()
    return manager.info_card(info, event.user_id)


@plugin.handle({"我的道具"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    user, account = manager.account(event)
    props = Counter()
    props += user.bank
    props += account.bank
    if not props:
        return "您的仓库空空如也。"

    data = manager.props_data(props)
    if len(data) < 10 or event.single_arg() in {"信息", "介绍", "详情"}:
        info = bank_card(data)
    else:
        info = [prop_card(data)]
    return manager.info_card(info, event.user_id)


@plugin.handle({"股票查询", "投资查询"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    user, account = manager.account(event)
    data = manager.invest_data(user.invest)
    if data:
        return manager.info_card([invest_card(data, f"股票信息:{account.name}")], event.user_id)
    return "您的仓库空空如也。"


@plugin.handle({"群金库"}, {"user_id", "group_id", "permission"})
async def _(event: Event):
    if event.is_private() or not (args := event.args_parse()):
        return
    command, N = args[:2]
    user_id = event.user_id
    group_id = event.group_id
    group = manager.data.group(group_id)
    if command == "查看":
        data = manager.props_data(group.bank)
        if len(data) < 6:
            info = bank_card(data)
        else:
            info = [prop_card(data, "群金库")]
        data = manager.invest_data(group.invest)
        if data:
            info.append(invest_card(data, "群投资"))
        return manager.info_card(info, user_id) if info else "群金库是空的"
    sign, name = command[0], command[1:]
    if not name:
        pass
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


@plugin.handle({"群资料卡"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    """
    群资料卡
    """
    group_name = event.single_arg()
    if group_name and (group := manager.group_library.get(group_name)):
        pass
    else:
        user, group_account = manager.account(event)
        group = manager.data.group(group_account.group_id)
    info = []
    lines = [
        f"{datetime.fromtimestamp(stock.time).strftime('%Y年%m月%d日')if (stock :=group.stock) else '未发行'}",
        f"等级 {group.level}",
        f"成员 {len(group.accounts_map)}",
    ]
    info.append(
        avatar_card(
            await download_url(avatar_url) if (avatar_url := group.avatar_url) else None,
            group.nickname,
            lines,
        )
    )
    if ranklist := group.extra.get("revolution_achieve"):
        ranklist = list(ranklist.items())
        ranklist.sort(key=lambda x: x[1], reverse=True)

        def result(user_id, n):
            account_id = group.accounts_map.get(user_id)
            if account_id and (account := manager.data.account_dict.get(account_id)):
                nickname = nickname if len(nickname := account.name) < 7 else nickname[:6] + ".."
            else:
                nickname = "已注销"
            return f"{nickname}[nowrap]\n[right]{n}次"

        info.append(text_to_image("\n".join(result(*seg) for seg in ranklist[:10]) + endline("路灯挂件榜")))
    if record := group.extra.get("stock_record"):
        info.append(candlestick((9.5, 3), 12, record))
    if data := manager.props_data(group.bank):
        info.append(prop_card(data, "群金库"))
    if data := manager.invest_data(group.invest):
        info.append(invest_card(data, "群投资"))
    if group.message:
        info.append(text_to_image("\n".join(group.message) + endline("Message"), 30, autowrap=True))
        group.message.clear()
    return manager.info_card(info, event.user_id)


# 超管指令
@plugin.handle({"获取"}, {"user_id", "group_id", "nickname", "permission"})
@Check().superuser().check
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


@plugin.handle({"冻结资产"}, {"user_id", "group_id", "permission", "at"})
@Check().superuser().at().check
async def _(event: Event):
    user_id = event.user_id
    group_id = event.group_id
    user, account = manager.locate_account(event.at[0], group_id)
    confirm = "".join(str(random.randint(0, 9)) for _ in range(4))

    @plugin.temp_handle(f"{confirm} {user_id} {group_id}", {"user_id", "group_id", "permission"})
    async def _(temp_event: Event, finish):
        if temp_event.user_id != user_id or temp_event.group_id != group_id:
            return
        finish()
        if temp_event.raw_command != confirm:
            return "【冻结】已取消。"
        bank = Counter()
        bank += user.bank
        user.bank.clear()
        accounts_map = user.accounts_map.copy()
        for _group_id, account_id in accounts_map.items():
            account = manager.data.account_dict[account_id]
            level = manager.data.group(_group_id).level
            bank += {k: v * level for k, v in account.bank.items()}
            manager.data.cancel_account(account_id)
        info = []
        if data := [(prop, v) for k, v in bank.items() if (prop := manager.props_library.get(k))]:
            info.append(prop_card(data, "已删除道具"))
        if data := [(stock, v) for k, v in user.invest.items() if (group := manager.group_library.get(k)) and (stock := group.stock)]:
            info.append(invest_card(data, "已删除股票"))
        user.invest.clear()
        if info:
            return ["冻结完成", manager.info_card(info, user_id)]
        return "冻结完成,目标没有任何资产"

    return f"您即将冻结 {account.name}（{user.id}），请输入{confirm}来确认。"
