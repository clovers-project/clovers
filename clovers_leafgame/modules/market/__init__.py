import time
import math
import random
from io import BytesIO
from collections import Counter
from clovers_apscheduler import scheduler
from clovers_utils.tools import item_name_rule, gini_coef, format_number
from clovers_leafgame.core.clovers import Event, to_me, group_admin, superuser
from clovers_leafgame.core.data import Stock, Group
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import GOLD, LICENSE, STD_GOLD
from clovers_leafgame.output import text_to_image, endline, invest_card, prop_card
from clovers_core.config import config as clovers_config
from .config import Config

config = Config.parse_obj(clovers_config.get(__package__, {}))

revolt_gold = config.revolt_gold
revolt_gini = config.revolt_gini
revolt_cd = config.revolt_cd
company_public_gold = config.company_public_gold


@plugin.handle({"重置签到", "领取金币"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event):
    user, account = manager.account(event)
    user.avatar_url = event.avatar
    extra = account.extra
    if not extra.setdefault("revolution", True):
        return "你没有待领取的金币"
    N = random.randint(*revolt_gold)
    GOLD.deal(account.bank, N)
    extra["revolution"] = False
    return f"这是你重置后获得的金币！你获得了 {N} 金币"


@plugin.handle({"金币转移"}, {"user_id", "group_id"})
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    group_name, xfer = args[:2]
    group_in = manager.group_library.get(group_name)
    if not group_in:
        return f"没有 {group_name} 的注册信息"
    user = manager.data.user(event.user_id)
    if not (receiver_account_id := user.accounts_map.get(group_in.id)):
        return f"你在{group_in.nickname}没有帐户"
    group_out = manager.data.group(event.group_id or user.connect)
    if not (sender_account_id := user.accounts_map.get(group_out.id)):
        return "你在本群没有帐户"
    if (n := group_out.bank.get(GOLD.id, 0)) < company_public_gold:
        return f"本群金币过少（{n}<{company_public_gold}），无法完成结算"
    bank_out = manager.data.account_dict[sender_account_id].bank
    bank_in = manager.data.account_dict[receiver_account_id].bank
    if xfer < 0:
        bank_out, bank_in = bank_in, bank_out
        group_out, group_in = group_in, group_out
        xfer = -xfer
    ExRate = group_in.level / group_out.level
    receipt = xfer * ExRate
    if receipt < 1:
        return f"转入金币{round(receipt,2)}不可小于1枚（汇率：{round(ExRate,2)}）。"
    if n := GOLD.deal(bank_out, -xfer):
        return f"数量不足。\n——你还有{n}枚金币。"
    GOLD.deal(bank_in, int(receipt))
    return f"{group_out.nickname}向{group_in.nickname}转移{xfer} 金币\n汇率 {round(ExRate,2)}\n实际到账金额 {receipt}"


@plugin.handle({"市场注册", "公司注册", "注册公司"}, {"group_id", "to_me", "permission", "group_avatar"})
@to_me.decorator
@group_admin.decorator
async def _(event: Event):
    group_id = event.group_id
    group = manager.data.group(group_id)
    group.avatar_url = event.group_avatar
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
    if stock_value < company_public_gold:
        return f"本群金币（{stock_value}）小于{company_public_gold}，注册失败。"
    gini = gini_coef(wealths[:-1])
    if gini > revolt_gini:
        return f"本群基尼系数（{round(gini,3)}）过高，注册失败。"
    stock.id = group_id
    stock.name = stock_name
    stock.time = time.time()
    level = group.level = (sum(ra.values()) if (ra := group.extra.get("revolution_achieve")) else 0) + 1
    issuance = 20000 * level
    group.invest[group_id] = issuance - stock.issuance
    group.bank[GOLD.id] = group.bank.get(GOLD.id, 0)
    stock.issuance = issuance
    stock.floating = stock.value = (stock_value) * level
    manager.group_library.set_item(group.id, {stock_name}, group)
    return f"{stock.name}发行成功，发行价格为{format_number(stock.value/ 20000)}金币"


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


@plugin.handle({"购买", "发行购买"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    stock_name, buy, limit = args
    stock_group = manager.group_library.get(stock_name)
    if not stock_group:
        return f"没有 {stock_name} 的注册信息"
    stock = stock_group.stock
    buy = min(stock_group.invest.get(stock.id, 0), buy)
    if buy < 1:
        return "已售空，请等待结算。"
    group = manager.group_library.get(stock_name)
    if (n := group.bank.get(GOLD.id, 0)) < company_public_gold:
        return f"本群金币过少（{n}<{company_public_gold}），无法完成结算"
    stock_value = sum(manager.group_wealths(stock.id, GOLD.id)) * stock_group.level
    user, account = manager.account(event)
    my_STD_GOLD = account.bank.get(GOLD.id, 0) * group.level
    issuance = stock.issuance
    value = 0.0
    actual_buy = 0
    unit = max(stock.floating, stock_value) / issuance
    for _ in range(buy):
        if unit > limit:
            tip = f"价格超过限制（{limit}）。"
            break
        value += unit
        if value > my_STD_GOLD:
            tip = f"你的金币不足（{my_STD_GOLD}）。"
            break
        unit += value / issuance
        actual_buy += 1
    else:
        tip = "交易成功！"
    actual_gold = math.ceil(value / group.level)
    GOLD.force_deal(account.bank, -actual_gold)
    GOLD.force_deal(group.bank, math.ceil(value / stock_group.level))
    stock.force_deal(group.bank, -actual_buy)
    stock.force_deal(user.bank, actual_buy)
    stock.floating += value
    stock.value = stock_value + value
    output = BytesIO()
    text_to_image(
        f"{stock.name}\n----"
        f"\n数量：{actual_buy}"
        f"\n单价：{round(value/actual_buy,2)}"
        f"\n总计：{round(value,2)}（{actual_gold}）" + endline(tip),
        width=440,
        bg_color="white",
    ).save(output, format="png")
    return output


@plugin.handle({"出售", "卖出", "结算"}, {"user_id"})
async def _(event: Event):
    user = manager.data.user(event.user_id)
    stock_name, n, quote = event.args_parse()
    stock_group = manager.group_library.get(stock_name)
    if not stock_group:
        return f"没有 {stock_name} 的注册信息"
    stock_name = stock_group.nickname
    stock_id = stock_group.id
    my_stock = user.invest.get(stock_id, 0)
    if my_stock < n:
        return f"你的账户中没有足够的{stock_name}（{my_stock}）。"
    user_id = user.id
    exchange = stock_group.stock.exchange
    if n < 1:
        if exchange.get(user_id):
            del exchange[user_id]
            return "交易信息已注销。"
        else:
            return "交易信息无效。"
    if not quote:
        quote = 0.0
    if user_id in exchange:
        tip = "交易信息已修改。"
    else:
        tip = "交易信息发布成功！"
    exchange[user_id] = (n, quote)
    output = BytesIO()
    text_to_image(
        f"{stock_name}\n----\n报价：{quote or '抛售'}\n数量：{n}" + endline(tip),
        width=440,
        bg_color="white",
    ).save(output, format="png")
    return output


@plugin.handle({"市场信息"}, {"user_id", "group_id"})
async def _(event: Event):
    group_ids = manager.group_library._key_indices.keys()
    groups = (manager.group_library[group_id] for group_id in group_ids)
    data = [(group.stock, group.invest.get(group.stock.id, 0)) for group in groups]
    if not data:
        return "市场为空"
    data.sort(key=lambda x: x[0].value, reverse=True)
    return manager.info_card([invest_card(data)], event.user_id)


@plugin.handle({"继承公司账户", "继承群账户"}, {"user_id", "permission"})
@superuser.decorator
async def _(event: Event):
    args = event.raw_event.args
    if len(args) != 3:
        return
    arrow = args[1]
    if arrow == "->":
        deceased = args[0]
        heir = args[2]
    elif arrow == "<-":
        heir = args[0]
        deceased = args[2]
    else:
        return "请输入:被继承群 -> 继承群"
    deceased_group = manager.group_library.get(deceased)
    if not deceased_group:
        return f"被继承群:{deceased} 不存在"
    heir_group = manager.group_library.get(heir)
    if not heir_group:
        return f"继承群:{heir} 不存在"
    if deceased_group is heir_group:
        return "无法继承自身"
    ExRate = deceased_group.level / heir_group.level
    # 继承群金库
    invest_group = Counter(deceased_group.invest)
    heir_group.invest = dict(Counter(heir_group.invest) + invest_group)
    bank_group = Counter({k: int(v * ExRate) if manager.props_library[k].domain == 1 else v for k, v in deceased_group.bank.items()})
    heir_group.bank = dict(Counter(heir_group.bank) + bank_group)
    # 继承群员账户
    all_bank_private = Counter()
    for deceased_user_id, deceased_account_id in deceased_group.accounts_map.items():
        deceased_account = manager.data.account_dict[deceased_account_id]
        bank = Counter({k: int(v * ExRate) for k, v in deceased_account.bank.items()})
        if deceased_user_id in heir_group.accounts_map:
            all_bank_private += bank
            heir_account_id = heir_group.accounts_map[deceased_user_id]
            heir_account = manager.data.account_dict[heir_account_id]
            heir_account.bank = dict(Counter(heir_account.bank) + bank)
        else:
            bank_group += bank
            heir_group.bank = dict(Counter(heir_group.bank) + bank)
    del manager.group_library[deceased_group.id]
    manager.data.cancel_group(deceased_group.id)
    info = []
    info.append(invest_card([(manager.group_library[k].stock, v) for k, v in invest_group.items()], "群投资继承"))
    info.append(prop_card([(manager.props_library[k], v) for k, v in bank_group.items()], "群金库继承"))
    info.append(prop_card([(manager.props_library[k], v) for k, v in all_bank_private.items()], "个人总继承"))
    return manager.info_card(info, event.user_id)


@plugin.handle({"刷新市场"}, {"permission"})
@superuser.decorator
@scheduler.scheduled_job("cron", minute="*/5", misfire_grace_time=120)
async def _():
    def stock_update(group: Group):
        stock = group.stock
        level = group.level
        # 资产更新
        wealths = manager.group_wealths(group.id, GOLD.id)
        stock_value = stock.value = sum(wealths) * level
        floating = stock.floating
        if not floating or math.isnan(floating):
            stock.floating = float(stock_value)
            return f"{stock.name} 已初始化"
        # 股票价格变化：趋势性影响（正态分布），随机性影响（平均分布），向债务价值回归
        floating += floating * random.gauss(0, 0.03)
        floating += stock_value * random.uniform(-0.1, 0.1)
        floating += (stock_value - floating) * 0.05
        # 股票浮动收入
        group.bank[GOLD.id] = int(wealths[-1] * floating / stock.floating)
        # 结算交易市场上的股票
        issuance = stock.issuance
        std_value = 0
        for user_id, exchange in stock.exchange.items():
            user = manager.data.user(user_id)
            n, quote = exchange
            value = 0.0
            settle = 0
            if quote:
                for _ in range(n):
                    unit = floating / issuance
                    if unit < quote:
                        break
                    value += quote
                    floating -= quote
                    settle += 1
            else:
                for _ in range(n):
                    unit = max(floating / issuance, 0.0)
                    value += unit
                    floating -= unit
                settle = n
            if settle == 0:
                continue
            stock.exchange[user_id] = (n - settle, quote)
            stock.force_deal(user.invest, -settle)
            stock.force_deal(group.invest, settle)
            value = int(value)
            STD_GOLD.force_deal(user.bank, value)
            std_value += value
        GOLD.force_deal(group.bank, -int(std_value / level))
        stock.exchange = {user_id: exchange for user_id, exchange in stock.exchange.items() if exchange[0] > 0}
        # 更新浮动价格
        stock.floating = floating
        # 记录价格历史
        if not (stock_record := group.extra.get("stock_record")):
            stock_record = [(0.0, 0.0) for _ in range(720)]
        stock_record.append((time.time(), floating / issuance))
        stock_record = stock_record[-720:]
        group.extra["stock_record"] = stock_record
        return f"{stock.name} 更新成功！"

    groups = [group for group in manager.data.group_dict.values() if group.stock.name and group.stock.issuance]
    log = [stock_update(group) for group in groups]
    print("\n".join(log))
