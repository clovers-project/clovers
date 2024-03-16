import time
import math
import random
from io import BytesIO
from clovers_utils.tools import item_name_rule, gini_coef, format_number
from clovers_leafgame.core.clovers import Event, to_me, group_admin
from clovers_leafgame.core.data import Stock, Group
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.item import GOLD, LICENSE
from clovers_leafgame.output import text_to_image, endline, invest_card
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
    if extra.setdefault("revolution", False):
        return "你没有待领取的金币"
    N = random.randint(*revolt_gold)
    GOLD.deal(account.bank, N)
    extra["revolution"] = True
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
    group.bank[GOLD.id] = group.bank.get(GOLD.id, 0) + company_public_gold
    stock.issuance = issuance
    stock.fixed = stock.floating = stock.stock_value = (stock_value + company_public_gold) * level
    manager.group_library.set_item(group.id, {stock_name}, group)
    return f"{stock.name}发行成功，发行价格为{format_number(stock.stock_value/ 20000)}金币"


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
    stock.stock_value = stock_value + value
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
    exchange[user_id] = (n, quote)
    if user_id in exchange:
        tip = "交易信息已修改。"
    else:
        tip = "交易信息发布成功！"
    output = BytesIO()
    text_to_image(f"{stock_name}\n----\n报价：{quote}\n数量：{n}" + endline(tip), width=440, bg_color="white").save(output, format="png")
    return output


@plugin.handle({"市场信息"}, {"user_id", "group_id"})
async def _(event: Event):
    group_ids = manager.group_library._key_indices.keys()
    groups = (manager.group_library[group_id] for group_id in group_ids)
    data = [(group.stock, group.invest.get(group.stock.id, 0)) for group in groups]
    if not data:
        return "市场为空"
    data.sort(key=lambda x: x[0].stock_value, reverse=True)
    return manager.info_card([invest_card(data)], event.user_id)


def stock_update(stock: Stock):
    company_id = company.company_id
    # 更新全群金币数
    group_gold = company.group_gold = Manager.group_wealths(company_id, company.level)
    # 固定资产回归值 = 全群金币数 + 股票融资
    SI = company.issuance
    line = group_gold * (2 - company.stock / SI)
    # 公司金币数回归到固定资产回归值
    gold = company.gold
    gold += (line - gold) / 96
    company.gold = gold
    if gold > 0.0:
        # 股票价格变化 = 趋势性影响（正态分布） + 随机性影响（平均分布）
        float_gold = company.float_gold
        float_gold += float_gold * random.gauss(0, 0.03) + gold * random.uniform(-0.1, 0.1)
        # 股票价格向债务价值回归
        deviation = gold - float_gold
        float_gold += 0.1 * deviation * abs(deviation / gold)
        # Nan检查
        float_gold = group_gold if math.isnan(float_gold) else float_gold
        # 自动结算交易市场上的股票
        for user_id, exchange in company.exchange.items():
            if not (user := Manager.get_user(user_id)):
                exchange.n = 0
                continue
            if not (group_account := user.group_accounts.get(exchange.group_id)):
                exchange.n = 0
                continue

            quote = exchange.quote
            value = 0.0
            inner_settle = 0
            for _ in range(exchange.n):
                unit = float_gold / SI
                if unit < quote:
                    break
                value += quote
                float_gold -= quote
                inner_settle += 1

            if not inner_settle:
                continue
            # 结算股票
            company.Buyback(group_account, inner_settle)
            # 结算金币
            gold = int(value / Manager.locate_group(exchange.group_id).company.level)
            user.gold += gold
            group_account.gold += gold
            company.gold -= value
        # 清理无效交易信息
        company.exchange = {user_id: exchange for user_id, exchange in company.exchange.items() if exchange.n > 0}
    else:
        float_gold = 0.0
    # 更新浮动价格
    company.float_gold = float_gold
    # 记录价格历史
    Manager.market_history.record(company_id, (time.time(), group_gold / SI, float_gold / SI))


def update():
    """
    刷新市场
    """
    log = []
    company_ids = set([company_index[company_id] for company_id in company_index])
    for company_id in company_ids:
        company = Manager.locate_group(company_id).company
        company_update(company)
        log.append(f"{company.company_name} 更新成功！")

    return "\n".join(log)
