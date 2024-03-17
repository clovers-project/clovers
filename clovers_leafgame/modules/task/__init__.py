from datetime import datetime
from collections import Counter
from clovers_apscheduler import scheduler
from clovers_leafgame.core.clovers import Event, superuser
from clovers_leafgame.main import plugin, manager


def verification():
    """
    数据校验
    """
    user_dict = manager.data.user_dict
    group_dict = manager.data.group_dict
    account_dict = manager.data.account_dict
    props_library = manager.props_library
    stock_check = Counter()
    # 检查 user_dict
    for user_id, user in user_dict.items():
        user.id = user_id
        # 清理未持有的道具
        user.bank = {k: v for k, v in user.bank.items() if v > 0 and k in props_library}
        # 删除无效及未持有的股票
        invest = user.invest = {k: v for k, v in user.invest.items() if k in group_dict and v > 0}
        # 股票数检查
        stock_check += Counter(invest)
        for group_id, accounts_id in user.accounts_map.items():
            account = account_dict[accounts_id]
            account.user_id = user_id
            account.group_id = group_id
            # 清理未持有的道具
            account.bank = {k: v for k, v in account.bank.items() if v > 0 and k in props_library}
            group_dict[group_id].accounts_map[user_id] = accounts_id
    # 检查group_data
    for group in group_dict.values():
        # 删除无效及未持有的股票
        group.invest = {k: v for k, v in group.invest.items() if k in group_dict and v > 0}
        stock_check += Counter(group.invest)

    for group_id, group in group_dict.items():
        # 修正公司等级
        group.level = sum(group.extra.setdefault("revolution_achieve", {}).values()) + 1
        # 修正股票库存
        group.stock.id = group_id
        issuance = 20000 * group.level
        group.stock.issuance = issuance
        group.invest[group_id] = issuance - stock_check[group_id]
        # 修正交易市场
        group.stock.exchange = {
            user_id: exchange for user_id, exchange in group.stock.exchange.items() if exchange[0] > 0 and user_id in user_dict
        }


# 数据验证
@plugin.handle({"数据验证"}, {"permission"})
@superuser.decorator
async def _(event: Event):
    verification()
    print("数据已验证")


@plugin.handle({"保存游戏"}, {"permission"})
@superuser.decorator
@scheduler.scheduled_job("cron", minute="*/10", misfire_grace_time=120)
async def _():
    manager.save()
    print("游戏数据已保存！")


@plugin.handle({"刷新每日"}, {"permission"})
@superuser.decorator
@scheduler.scheduled_job("cron", hour=0, misfire_grace_time=120)
async def _():
    verification()
    revolution_today = datetime.today().weekday() in {4, 5, 6}
    for user in manager.data.user_dict.values():
        user.bank = {k: min(v - 1) if prop.flow == 1 else v for k, v in user.bank.items() if (prop := manager.props_library.get(k))}
    for account in manager.data.account_dict.values():
        # 周末刷新重置签到
        account.extra["revolution"] = revolution_today
        # 群内道具有效期 - 1天
        account.bank = {k: min(v - 1) if prop.flow == 1 else v for k, v in account.bank.items() if (prop := manager.props_library.get(k))}
    print("每日签到已刷新")


# 数据备份
@plugin.handle({"数据备份"}, {"permission"})
@superuser.decorator
@scheduler.scheduled_job("cron", hour="*/4", misfire_grace_time=120)
async def _():
    manager.backup()
    print(manager.clean_backup(604800))
