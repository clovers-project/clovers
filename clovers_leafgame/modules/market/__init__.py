import time
import math
import random
from io import BytesIO
from collections import Counter
from clovers_apscheduler import scheduler
from clovers.utils.tools import gini_coef, format_number
from clovers_leafgame.core.clovers import Event, Check
from clovers_leafgame.core.data import Group, Stock
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import GOLD, LICENSE, STD_GOLD, item_name_rule
from clovers_leafgame.output import text_to_image, endline, invest_card, prop_card
from clovers.core.config import config as clovers_config
from .config import Config

config_key = __package__
config_data = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config_data.dict()


revolt_gold = config_data.revolt_gold
revolt_gini = config_data.revolt_gini
revolt_cd = config_data.revolt_cd
company_public_gold = config_data.company_public_gold


@plugin.handle({"重置签到", "领取金币"}, {"user_id", "group_id", "nickname", "avatar"})
async def _(event: Event):
    user, account = manager.account(event)
    user.avatar_url = event.avatar
    extra = account.extra
    if not extra.setdefault("revolution", True):
        return "你没有待领取的金币"
    n = random.randint(*revolt_gold)
    GOLD.deal(account.bank, n)
    extra["revolution"] = False
    return f"这是你重置后获得的金币！你获得了 {n} 金币"


@plugin.handle({"金币转入"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    n = event.args_to_int()
    if n == 0:
        return
    user, account = manager.account(event)
    level = manager.data.group(event.group_id).level
    if n > 0:
        n_out = n * level
        if n_out > user.bank[STD_GOLD.id]:
            n_out = user.bank[STD_GOLD.id]
            n_in = int(user.bank[STD_GOLD.id] / level)
        else:
            n_in = n
        user.bank[STD_GOLD.id] -= n_out
        account.bank[GOLD.id] += n_in
        return f"你成功将{n_out}枚标准金币兑换为{n_in}枚金币"
    else:
        n_out = n
        if n_out > account.bank[GOLD.id]:
            n_out = account.bank[GOLD.id]
            n_in = account.bank[GOLD.id] * level
        else:
            n_in = n * level
        user.bank[STD_GOLD.id] += n_in
        account.bank[GOLD.id] -= n_out
        return f"你成功将{n_out}枚金币兑换为{n_in}枚标准金币"


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
    if (n := group_out.bank[GOLD.id]) < company_public_gold:
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
@Check().to_me().group_admin().check
async def _(event: Event):
    group_id = event.group_id
    group = manager.data.group(group_id)
    group.avatar_url = event.group_avatar
    stock = group.stock
    if stock:
        return f"本群已在市场注册，注册名：{stock.name}"
    stock_name = event.single_arg()
    if not stock_name:
        return "请输入注册名"
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
    level = group.level = (sum(ra.values()) if (ra := group.extra.get("revolution_achieve")) else 0) + 1
    stock_value *= level
    stock = Stock(
        id=group_id,
        name=stock_name,
        value=stock_value,
        floating=stock_value,
        issuance=20000 * level,
        time=time.time(),
    )
    manager.group_library.set_item(group.id, {stock_name}, group)
    return f"{stock.name}发行成功，发行价格为{format_number(stock.value/ 20000)}金币"


@plugin.handle({"公司重命名"}, {"group_id", "to_me", "permission"})
@Check().to_me().group_admin().check
async def _(event: Event):
    group = manager.data.group(event.group_id)
    stock = group.stock
    if not stock:
        return "本群未在市场注册，不可重命名。"
    stock_name = event.single_arg()
    if not stock_name:
        return "请输入注册名"
    if check := item_name_rule(stock_name):
        return check
    if LICENSE.deal(group.bank, -1):
        return f"本群仓库缺少【{LICENSE.name}】"
    old_name = stock.name
    stock.name = stock_name
    manager.group_library.set_item(group.id, {stock_name}, group)
    return f"【{old_name}】已重命名为【{stock_name}】"


@plugin.handle({"购买", "发行购买"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    stock_name, buy, limit = args
    stock_group = manager.group_library.get(stock_name)
    if not stock_group or not (stock := stock_group.stock):
        return f"没有 {stock_name} 的注册信息"
    buy = min(stock_group.invest[stock.id], buy)
    if buy < 1:
        return "已售空，请等待结算。"
    if (n := stock_group.bank[GOLD.id]) < company_public_gold:
        return f"本群金币过少（{n}<{company_public_gold}），无法完成结算"
    stock_level = stock_group.level
    stock_value = sum(manager.group_wealths(stock.id, GOLD.id)) * stock_level + stock_group.bank[STD_GOLD.id]
    user, account = manager.account(event)
    group = manager.data.group(account.group_id)
    level = group.level
    account_STD_GOLD = account.bank[GOLD.id] * level
    my_STD_GOLD = user.bank[STD_GOLD.id] + account_STD_GOLD
    issuance = stock.issuance
    floating = stock.floating
    limit = limit or float("inf")
    value = 0.0
    _buy = 0
    for _ in range(buy):
        unit = max(floating, stock_value) / issuance
        if unit > limit:
            tip = f"价格超过限制（{limit}）。"
            break
        value += unit
        if value > my_STD_GOLD:
            value -= unit
            tip = f"你的金币不足（{my_STD_GOLD}）。"
            break
        floating += unit
        _buy += 1
    else:
        tip = "交易成功！"

    int_value = math.ceil(value)
    user.bank[STD_GOLD.id] -= int_value
    if (n := user.bank[STD_GOLD.id]) < 0:
        user.bank[STD_GOLD.id] = 0
        account_STD_GOLD += n
        account.bank[GOLD.id] = math.ceil(account_STD_GOLD / level)
        user.add_message(f"购买{_buy}份{stock_name}需要花费{int_value}枚标准金币，其中{-n}枚来自购买群账户，汇率（{level}）")
    user.invest[stock.id] += _buy
    stock_group.bank[GOLD.id] += math.ceil(value / stock_level)
    group.invest[stock.id] -= _buy
    stock.floating = floating
    stock.value = stock_value + int_value
    output = BytesIO()
    text_to_image(
        f"{stock.name}\n----" f"\n数量：{_buy}" f"\n单价：{round(value/_buy,2)}" f"\n总计：{int_value}" + endline(tip),
        width=440,
        bg_color="white",
    ).save(output, format="png")
    return output


@plugin.handle({"出售", "卖出", "结算"}, {"user_id"})
async def _(event: Event):
    if not (args := event.args_parse()):
        return
    stock_name, n, quote = args
    user = manager.data.user(event.user_id)
    stock_group = manager.group_library.get(stock_name)
    if not stock_group or not (stock := stock_group.stock):
        return f"没有 {stock_name} 的注册信息"
    stock_name = stock_group.nickname
    my_stock = min(user.invest[stock.id], n)
    user_id = user.id
    exchange = stock.exchange
    if my_stock < 1:
        if user_id in exchange:
            del exchange[user_id]
            return "交易信息已注销。"
        else:
            return "交易信息无效。"
    if user_id in exchange:
        tip = "交易信息已修改。"
    else:
        tip = "交易信息发布成功！"
    exchange[user_id] = (n, quote or 0.0)
    output = BytesIO()
    text_to_image(
        f"{stock_name}\n----\n报价：{quote or '自动出售'}\n数量：{n}" + endline(tip),
        width=440,
        bg_color="white",
    ).save(output, format="png")
    return output


@plugin.handle({"市场信息"}, {"user_id"})
async def _(event: Event):
    data = [(stock, group.invest[stock.id]) for group in manager.data.group_dict.values() if (stock := group.stock)]
    if not data:
        return "市场为空"
    data.sort(key=lambda x: x[0].value, reverse=True)
    return manager.info_card([invest_card(data)], event.user_id)


@plugin.handle({"继承公司账户", "继承群账户"}, {"user_id", "permission"})
@Check().superuser().check
async def _(event: Event):
    args = event.args
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
    heir_group.invest = Counter(heir_group.invest) + invest_group
    bank_group = Counter({k: int(v * ExRate) if manager.props_library[k].domain == 1 else v for k, v in deceased_group.bank.items()})
    heir_group.bank = Counter(heir_group.bank) + bank_group
    # 继承群员账户
    all_bank_private = Counter()
    for deceased_user_id, deceased_account_id in deceased_group.accounts_map.items():
        deceased_account = manager.data.account_dict[deceased_account_id]
        bank = Counter({k: int(v * ExRate) for k, v in deceased_account.bank.items()})
        if deceased_user_id in heir_group.accounts_map:
            all_bank_private += bank
            heir_account_id = heir_group.accounts_map[deceased_user_id]
            heir_account = manager.data.account_dict[heir_account_id]
            heir_account.bank = Counter(heir_account.bank) + bank
        else:
            bank_group += bank
            heir_group.bank = Counter(heir_group.bank) + bank
    del manager.group_library[deceased_group.id]
    manager.data.cancel_group(deceased_group.id)
    info = []
    info.append(invest_card(manager.invest_data(invest_group), "群投资继承"))
    info.append(prop_card(manager.props_data(bank_group), "群金库继承"))
    info.append(prop_card(manager.props_data(all_bank_private), "个人总继承"))
    return manager.info_card(info, event.user_id)


@plugin.handle({"刷新市场"}, {"permission"})
@Check().superuser().check
@scheduler.scheduled_job("cron", minute="*/5", misfire_grace_time=120)
async def _():
    def stock_update(group: Group):
        stock = group.stock
        if not stock:
            return f"{group.id} 更新失败"
        level = group.level
        # 资产更新
        wealths = manager.group_wealths(group.id, GOLD.id)
        stock_value = stock.value = sum(wealths) * level + group.bank[STD_GOLD.id]
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
        now_time = time.time()
        clock = time.strftime("%H:%M", time.localtime(now_time))
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
            if settle < n:
                stock.exchange[user_id] = (n - settle, quote)
            user.invest[stock.id] -= settle
            group.invest[stock.id] += settle
            user.bank[STD_GOLD.id] += int(value)
            user.message.append(
                f"【交易市场 {clock}】收入{value}标准金币。\n{stock.name}已出售{settle}/{n}，报价{quote or format_number(value/settle)}。"
            )
            std_value += value
        group.bank[GOLD.id] -= int(std_value / level)
        stock.exchange = {user_id: exchange for user_id, exchange in stock.exchange.items() if exchange[0] > 0}
        # 更新浮动价格
        stock.floating = floating
        # 记录价格历史
        if not (stock_record := group.extra.get("stock_record")):
            stock_record = [(0.0, 0.0) for _ in range(720)]
        stock_record.append((now_time, floating / issuance))
        stock_record = stock_record[-720:]
        group.extra["stock_record"] = stock_record
        return f"{stock.name} 更新成功！"

    groups = (group for group in manager.data.group_dict.values() if group.stock and group.stock.issuance)
    print("\n".join(stock_update(group) for group in groups))
