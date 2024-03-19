import random
from collections import Counter
from clovers_leafgame.core.clovers import Event, to_me
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import Prop, GOLD, STD_GOLD
from .library import usage, gacha, AIR_PACK, RED_PACKET, DIAMOND
from clovers_leafgame.output import prop_card, bank_card
from .output import report_card

from clovers_core.config import config as clovers_config
from .config import Config

config = Config.parse_obj(clovers_config.get(__package__, {}))

gacha_gold = config.gacha_gold
packet_gold = config.packet_gold
luckey_min, luckey_max = config.luckey_coin


@plugin.handle(r"^(.+)连抽?卡?|单抽", {"user_id", "group_id", "nickname", "to_me"})
@to_me.decorator
async def _(event: Event):
    count = event.args_to_int()
    if not count:
        return
    count = 200 if count > 200 else 1 if count < 1 else count
    gold = count * gacha_gold
    user, account = manager.account(event)
    if n := GOLD.deal(account.bank, -gold):
        return f"{count}连抽卡需要{gold}金币，你的金币：{n}。"

    prop_data: list[list[tuple[Prop, int]]] = [[], [], []]
    report_data = {"prop_star": 0, "prop_n": 0, "air_star": 0, "air_n": 0}
    for prop_id, n in Counter(gacha() for _ in range(count)).items():
        prop = manager.props_library[prop_id]
        prop_data[prop.domain].append((prop, n))
        if prop.domain == 0:
            star_key = "air_star"
            n_key = "air_n"
        else:
            star_key = "prop_star"
            n_key = "prop_n"
            prop.deal(prop.locate_bank(user, account), n)
        report_data[star_key] += prop.rare * n
        report_data[n_key] += n
    if count < 10:
        return "你获得了" + "\n".join(f"({prop.rare}☆){prop.name}:{n}个" for seg in prop_data for prop, n in seg)
    else:
        info = [report_card(account.name, **report_data)]
        if report_data["prop_n"] == 0:
            AIR_PACK.deal(user.bank, 1)
            RED_PACKET.deal(account.bank, 10)
            GOLD.deal(account.bank, gold)
            info.append(prop_card([(AIR_PACK, 1), (GOLD, gold), (RED_PACKET, 10)], f"本次抽卡已免费"))
        if data := prop_data[2]:
            info.append(prop_card(data, "全局道具"))
        if data := prop_data[1]:
            info.append(prop_card(data, "群内道具"))
        if data := prop_data[0]:
            info.append(prop_card(data, "未获取"))

    return manager.info_card(info, user.id)


@usage("金币", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    if n := prop.deal(prop.locate_bank(*manager.account(event)), -count):
        return f"使用失败，你还有{n}枚金币。"
    return f"你使用了{count}枚金币。"


@usage("临时维护凭证", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    bank = prop.locate_bank(*manager.account(event))
    if prop.deal(bank, -1):
        return f"使用失败，你未持有{prop.name}"
    try:
        exec(extra.strip())
        return f"执行成功！"
    except Exception as e:
        prop.deal(bank, 1)
        return str(e)


@usage("测试金库", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    bank = prop.locate_bank(*manager.account(event))
    if prop.deal(bank, -1):
        return f"使用失败，你没有足够的{prop.name}"
    return "你获得了10亿金币，100万钻石。祝你好运！"


@usage("空气礼包", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user, account = manager.account(event)
    bank = prop.locate_bank(user, account)
    if n := prop.deal(bank, -count):
        return f"使用失败，你没有足够的{prop.name}（{n}）"
    data = [(prop, count) for prop in manager.props_library.values() if prop.domain == 0]
    bank += {prop.id: n for prop, n in data}
    return ["你获得了", manager.info_card(bank_card(data), user.id)]


@usage("随机红包", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user, account = manager.account(event)
    bank = prop.locate_bank(user, account)
    if n := prop.deal(bank, -count):
        return f"使用失败，你没有足够的{prop.name}（{n}）"
    gold = random.randint(*packet_gold) * count
    GOLD.deal(account.bank, gold)
    return f"你获得了{gold}金币。祝你好运~"


@usage("重开券", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user, account = manager.account(event)
    bank = prop.locate_bank(user, account)
    if prop.deal(bank, -1):
        return f"使用失败，你没有足够的{prop.name}"
    if (n := account.bank[GOLD.id]) < 0:
        std_n = n * manager.data.group(account.group_id).level
        user.bank[STD_GOLD.id] += std_n
        user.add_message(f"【{prop.name}】你在群内的欠款（{-std_n}枚标准金币）已转移到个人账户")
    data = [(p, n) for k, n in bank.items() if (p := manager.props_library.get(k))]
    manager.data.cancel_account(account.id)
    return ["你在本群的账户已重置，祝你好运~", manager.info_card([prop_card(data, "账户已重置")], user.id)]


@usage("幸运硬币", {"user_id", "group_id", "nickname", "Bot_Nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user, account = manager.account(event)
    count = min(count, account.bank[GOLD.id])
    if count < luckey_min:
        return f"使用失败，{prop.name}最小赌注为{luckey_min}金币"
    if count > luckey_max:
        return f"使用失败，{prop.name}最大赌注为{luckey_max}金币"
    bank = prop.locate_bank(user, account)
    if prop.deal(bank, -1):
        return f"使用失败，你没有足够的{prop.name}"
    GOLD.deal(account.bank, -count)

    if random.randint(0, 1) == 0:
        GOLD.deal(account.bank, count * 2)
        return f"你获得了{count}金币"
    else:
        RED_PACKET.deal(RED_PACKET.locate_bank(user, account), 1)
        return f"你失去了{count}金币。\n{event.event.kwargs['Bot_Nickname']}送你1个『随机红包』，祝你好运~"


@usage("超级幸运硬币", {"user_id", "group_id", "nickname", "Bot_Nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user, account = manager.account(event)
    bank = prop.locate_bank(user, account)
    if prop.deal(bank, -1):
        return f"使用失败，你没有足够的{prop.name}"
    gold = account.bank[GOLD.id]
    if random.randint(0, 1) == 0:
        account.bank[GOLD.id] *= 2
        return f"你获得了{gold}金币"
    else:
        account.bank[GOLD.id] = 0
        RED_PACKET.deal(RED_PACKET.locate_bank(user, account), 1)
        return f"你失去了{gold}金币。\n{event.event.kwargs['Bot_Nickname']}送你1个『随机红包』，祝你好运~"


@add_prop_extra("道具兑换券")
def _(event: Event, count: int) -> Result:
    user, group_account = Manager.locate_user(event)
    if not group_account:
        return "私聊未关联账户，请发送【关联账户】关联群内账户。"
    props_account = group_account.props
    prop_name = "道具兑换券"
    if len(event.args) == 1:
        pass
    elif len(event.args) == 2:
        if event.args[1].isdigit():
            count = int(event.args[1])
        else:
            prop_name = event.args[1]
    else:
        event.args = event.args[1:]
        prop_name, count, _ = event.args_parse()
    prop_code = get_prop_code(prop_name)
    if not prop_code:
        return f"没有【{prop_name}】这种道具。"
    if prop_code[0] == "0":
        return "不能兑换特殊道具。"
    # 购买道具兑换券，价格 50抽
    props_account.setdefault("62102", 0)
    buy = max(count - props_account["62102"], 0)
    gold = buy * gacha_gold * 50
    if group_account.gold < gold:
        return f"金币不足。你还有{group_account.gold}枚金币。（需要：{gold}）"
    # 购买结算
    group_account.gold -= gold
    props_account["62102"] += buy
    # 道具结算
    if prop_code[1] == "3":
        account = user
    else:
        account = group_account
    account.props[prop_code] = account.props.get(prop_code, 0) + count
    props_account["62102"] -= count
    if props_account["62102"] < 1:
        del props_account["62102"]
    return f"你获得了{count}个【{prop_name}】！（使用金币：{gold}）"
