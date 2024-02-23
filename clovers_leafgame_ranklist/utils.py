from collections.abc import Callable
from clovers_leafgame.main import manager
from clovers_leafgame.prop import GOLD
from clovers_leafgame.core.data import Bank, Account

RankKey = Callable[[str], int | float]


def ranklist(
    namelist: set[str],
    key: RankKey,
    reverse: bool = True,
):
    """
    用户排行榜
        param:
            key:从用户寻找可以排名的排名内容
    """
    data = [(k, v) for k in namelist if (v := key(k))]
    data.sort(key=lambda x: x[1], reverse=reverse)
    return data
