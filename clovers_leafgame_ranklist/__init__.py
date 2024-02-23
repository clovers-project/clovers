import re
import asyncio
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.core.clovers import Event
from clovers_leafgame.prop import library
from clovers_leafgame.core.utils import download_url
from .output import draw_rank


@plugin.handle(r"^.+排行.*", {"user_id", "group_id"})
async def _(event: Event):
    cmd_match = re.search(r"(.+)排行(.*)", event.raw_event.raw_command.strip())
    title = cmd_match.group(1)
    group_name = cmd_match.group(2) or event.group_id or manager.locate_user(event.user_id).connect
    group = manager.group_search(group_name)
    group_id = group.group_id if group else None
    if title == "路灯挂件":
        data = {}
        for group in manager.data.group_dict.values():
            for k, v in group.extra.setdefault("revolution_achieve"):
                data[k] = data.get(k, 0) + v
        ranklist = list(data.items())
        ranklist.sort(key=lambda x: x[1], reverse=True)
    else:
        if title.endswith("总"):
            namelist = manager.namelist()
            new_title = title[:-1]
            key = manager.rankkey(new_title)
            if not key:
                prop = library.search(new_title)
                if not prop or prop.domain != 1:
                    return
                key = lambda user_id: sum(
                    account.bank.get(prop.id, 0) * manager.locate_group(group_id).level
                    for group_id, account in manager.locate_user(user_id).accounts.items()
                )
        else:
            if not group_id:
                return
            namelist = manager.namelist(group_name)
            key = manager.rankkey(title)
            if not key:
                prop = library.search(title)
                if not prop:
                    return
                key = lambda user_id: prop.user_bank(manager.locate_user(user_id), group_id).get(prop.id, 0)
        ranklist = manager.ranklist(namelist, key)

    if not ranklist:
        return f"无数据，无法进行{title}排行"
    nickname_data = []
    rank_data = []
    task_list = []
    for user_id, v in ranklist[:20]:
        user = manager.locate_user(user_id)
        nickname_data.append(user.nickname(group_id))
        rank_data.append(v)
        task_list.append(download_url(user.avatar_url))
    avatar_data = await asyncio.gather(*task_list)
    return manager.info_card([draw_rank(list(zip(nickname_data, rank_data, avatar_data)))], event.user_id)
