import random
import asyncio
from collections import Counter
from clovers_leafgame.core.clovers import Event, Check
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import Prop, GOLD, STD_GOLD
from .core import usage, gacha, AIR_PACK, RED_PACKET
from clovers_leafgame.output import prop_card, bank_card
from .output import report_card

from clovers.core.config import config as clovers_config
from .config import Config

config_key = __package__
config_data = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config_data.dict()

gacha_gold = config_data.gacha_gold
packet_gold = config_data.packet_gold
luckey_min, luckey_max = config_data.luckey_coin
ticket_price = gacha_gold * 50


@plugin.handle(r"^(.+)连抽?卡?|单抽", {"user_id", "group_id", "nickname", "to_me"})
@Check().to_me().check
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
        return f"使用失败，你未持有{prop.name}"
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
    data = manager.props_data(bank)
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


@usage("道具兑换券", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    if extra:
        prop_name = extra.strip()
        target_prop = manager.props_library.get(prop_name)
        if not target_prop:
            return f"不存在道具【{prop_name}】"
        if target_prop.rare < 3:
            return f"无法兑换【{target_prop.name}】"
    else:
        target_prop = prop
    user, account = manager.account(event)
    bank = prop.locate_bank(user, account)
    # 购买道具兑换券，价格 50抽
    if count > bank[prop.id]:
        gold = ticket_price * (count - bank[prop.id])
        if n := GOLD.deal(account.bank, -gold):
            return f"金币不足。你还有{n}枚金币。（需要：{gold}）"
        bank[prop.id] = 0
    else:
        gold = 0
        bank[prop.id] -= count

    target_bank = target_prop.locate_bank(user, account)
    target_bank[target_prop.id] += count
    return f"你获得了{count}个【{target_prop.name}】！（使用金币：{gold}）"


@usage("绯红迷雾之书", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user_id = event.user_id
    bank = manager.data.user(user_id).bank
    if prop.deal(bank, -1):
        return f"使用失败，你未持有{prop.name}"
    group_id = event.group_id
    folders = {f.name: f for f in manager.backup_path.iterdir() if f.is_dir()}
    tip = "请输入你要回档的日期:\n" + "\n".join(folders.keys())
    key = f"{user_id} {group_id}"

    @plugin.temp_handle(key, {"user_id", "group_id"}, 30)
    @Check().locate(user_id, group_id).check
    async def _(event: Event, finish):
        date = event.raw_command
        folder = folders.get(date)
        if not folder:
            return tip
        files = {f.stem.split()[1].replace("-", ":"): f for f in folder.iterdir() if f.is_file()}
        tip2 = "请输入你要回档的时间:\n" + "\n".join(files.keys())
        finish()

        @plugin.temp_handle(key, {"user_id", "group_id"}, 30)
        @Check().locate(user_id, group_id).check
        async def _(event: Event, finish):
            clock = event.raw_command
            file = files.get(clock)
            if not file:
                return tip2
            manager.data.cancel_user(user_id)
            old_data = manager.data.load(file)
            user = manager.data.user_dict[user_id] = old_data.user(user_id)
            for account_id in user.accounts_map.values():
                manager.data.register(old_data.account_dict[account_id])
            finish()
            return f"你已经回档到{date} {clock}"

        return tip2

    return tip


@usage("恶魔轮盘", {"user_id", "group_id", "nickname", "Bot_Nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user_id = event.user_id
    group_id = event.group_id
    user = manager.data.user(user_id)
    if user.bank[prop.id] < 1:
        return f"使用失败，你没有足够的{prop.name}"
    group_id = event.group_id

    def ten_times_bank(bank: Counter):
        for k in bank.keys():
            bank[k] *= 10

    @plugin.temp_handle(f"{user_id} {group_id}", {"user_id", "group_id"}, 30)
    async def _(event_1: Event, finish):
        if event_1.user_id != user_id or event_1.group_id != group_id:
            return
        finish()
        if event_1.raw_command == "取消":
            return "恶魔轮盘已取消"
        if event_1.raw_command != "开枪":
            return

        async def result():
            bullet_lst = [0, 0, 0, 0, 0, 0]
            for i in random.sample([0, 1, 2, 3, 4, 5], random.randint(0, 6)):
                bullet_lst[i] = 1
            index = random.randint(0, 5)
            yield f"子弹列表{" ".join(str(x) for x in bullet_lst)}，你中了第{index+1}发子弹。"
            await asyncio.sleep(1)
            if bullet_lst[index] == 1:
                manager.data.cancel_user(user_id)
                yield "砰！一团火从枪口喷出，你从这个世界上消失了。"
                return
            counter = Counter()
            ten_times_bank(user.bank)
            user.bank[prop.id] = 1
            counter += user.bank
            for account_id in user.accounts_map.values():
                account = manager.data.account_dict[account_id]
                ten_times_bank(account.bank)
                counter += account.bank
            user.bank[STD_GOLD.id] += manager.stock_value(user.invest) * 10
            yield "咔！你活了下来..."
            yield [
                "这是你获得的道具",
                manager.info_card([prop_card(manager.props_data(counter))], user_id),
            ]

        return result()

    return "你手中的左轮枪已经装好了子弹，请开枪，或者取消。"
