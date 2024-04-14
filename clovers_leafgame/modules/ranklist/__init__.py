import re
import heapq
import asyncio
from collections import Counter
from collections.abc import Callable
from clovers_leafgame.core.clovers import Event
from clovers_leafgame.main import plugin, manager
from clovers.utils.tools import download_url
from .output import draw_rank


def rank_title(title) -> Callable[[str], int] | None:
    match title:
        case "胜场":
            return lambda locate_id: manager.data.extra.setdefault("win", Counter())[locate_id]
        case "连胜":
            return lambda locate_id: manager.data.extra.setdefault("win_achieve", Counter())[locate_id]
        case "败场":
            return lambda locate_id: manager.data.extra.setdefault("lose", Counter())[locate_id]
        case "败场":
            return lambda locate_id: manager.data.extra.setdefault("lose_achieve", Counter())[locate_id]


def all_ranklist(title: str):
    """总排名"""
    prop = manager.props_library.get(title)
    if not prop:
        return
    ranklist = []
    if prop.domain == 1:

        def std_value(prop_id: str, group_id: str, account_id: str):
            return manager.data.account_dict[account_id].bank[prop_id] * manager.data.group(group_id).level

        value = lambda prop_id: sum(std_value(prop_id, group_id, account_id) for group_id, account_id in user.accounts_map.items())
    else:
        value = lambda prop_id: user.bank[prop_id]
    for user_id in manager.data.user_dict.keys():
        user = manager.data.user(user_id)
        ranklist.append((user.name or user_id, value(prop.id), user.avatar_url))
    return ranklist


def group_ranklist(title: str, group_id: str):
    """群内排名"""
    prop = manager.props_library.get(title)
    if not prop:
        return
    group = manager.data.group_dict[group_id]
    ranklist = []
    for user_id in group.accounts_map.keys():
        user, account = manager.locate_account(user_id, group_id)
        ranklist.append((account.name or user.name or user_id, prop.N(user, account), user.avatar_url))
    return ranklist


@plugin.handle(r"^(.+)排行(.*)", {"user_id", "group_id"})
async def _(event: Event):
    title = event.args[0]
    if title.startswith("路灯挂件"):
        counter = Counter()
        for group in manager.data.group_dict.values():
            if not (revolution_achieve := group.extra.get("revolution_achieve")):
                continue
            counter.update(revolution_achieve)
        ranklist = []
        for user_id, value in counter.items():
            user = manager.data.user(user_id)
            ranklist.append((user.name or user_id, value, user.avatar_url))
    elif value := rank_title(title):
        ranklist = []
        for user_id in manager.data.user_dict.keys():
            user = manager.data.user(user_id)
            ranklist.append((user.name or user_id, value(user_id), user.avatar_url))
    elif title.endswith("总"):
        ranklist = all_ranklist(title[:-1])
    else:
        group_name = event.args[1] or event.group_id or manager.data.user(event.user_id).connect
        group = manager.group_library.get(group_name)
        group_id = group.id if group else None
        if not group_id:
            return
        ranklist = group_ranklist(title, group_id)
    if not ranklist:
        return f"无数据，无法进行{title}排行"
    ranklist = heapq.nlargest(20, ranklist, key=lambda x: x[1])
    nickname_data = []
    rank_data = []
    task_list = []
    for nickname, v, avatar_url in ranklist[:20]:
        nickname_data.append(nickname)
        rank_data.append(v)
        task_list.append(download_url(avatar_url))
    avatar_data = await asyncio.gather(*task_list)
    return manager.info_card([draw_rank(list(zip(nickname_data, rank_data, avatar_data)))], event.user_id)
