import time
import re
from collections.abc import Coroutine, Callable, Sequence
from clovers_utils.tools import to_int
from clovers_leafgame.main import manager
from clovers_leafgame.item import Prop, GOLD
from clovers_leafgame.core.clovers import Event
from clovers_core.config import config as clovers_config
from .config import Config

config = Config.parse_obj(clovers_config.get(__package__, {}))

default_bet = config.default_bet
timeout = config.timeout


class Session:
    """
    游戏场次信息
    """

    time: float
    group_id: str
    at: str | None = None
    p1_uid: str
    p1_nickname: str
    p2_uid: str | None = None
    p2_nickname: str | None = None
    round = 0
    next: str | None = None
    win: str | None = None
    bet: tuple[Prop, int] | None = None
    data: dict | None = None

    def __init__(self, group_id: str, user_id: str, nickname: str):
        self.time = time.time()
        self.group_id = group_id
        self.p1_uid = user_id
        self.p1_nickname = nickname

    def join(self, user_id: str, nickname: str):
        self.time = time.time()
        self.p2_uid = user_id
        self.p2_nickname = nickname

    def leave(self):
        self.time = time.time()
        self.p2_uid = None

    def nextround(self):
        self.time = time.time()
        self.round += 1
        self.next = self.p1_uid if self.next == self.p2_uid else self.p2_uid

    def create_check(self, user_id: str):
        overtime = time.time() - self.time
        if overtime > timeout:
            return
        p1_uid = self.p1_uid
        p2_uid = self.p2_uid
        if not p2_uid:
            return
        if p1_uid == user_id:
            return "你已发起了一场对决"
        if p2_uid == user_id:
            return "你正在进行一场对决"
        if p1_uid and p2_uid:
            return f"{self.p1_nickname} 与 {self.p2_nickname} 的对决还未结束，请等待比赛结束后再开始下一轮..."

    def create_info(self):
        if self.at:
            p2_nickname = self.p2_nickname or f"玩家{self.at[:4]}..."
            return f"{self.p1_nickname} 向 {p2_nickname} 发起挑战！\n请 {p2_nickname} 回复 接受挑战 or 拒绝挑战\n【{timeout}秒内有效】"
        else:
            return f"{self.p1_nickname} 发起挑战！\n回复 接受挑战 即可开始对局。\n【{timeout}秒内有效】"


class Game:
    name: str

    def __init__(self, name: str | None = None) -> None:
        self.name = name or "undefined"

    @staticmethod
    def args_parse(args: Sequence[str]) -> tuple[str, int, str]:
        match len(args):
            case 0:
                return "", 0, ""
            case 1:
                name = args[0]
                n = to_int(name)
                if n is None:
                    n = 0
                else:
                    name = ""
                return name, n, ""
            case 2:
                name, n = args
                return name, to_int(n) or 0, ""
            case _:
                name, n, arg = args[:3]
                return name, to_int(n) or 0, arg

    def create(self, place: dict[str, Session]):
        def decorator(func: Callable[[Session, str], Coroutine]):
            async def wrapper(event: Event):
                user, account = manager.account(event)
                group_id = account.group_id
                user.connect = group_id
                user_id = user.id
                if (session := place.get(group_id)) and (tip := session.create_check(user_id)):
                    return tip
                prop_name, n, arg = self.args_parse(event.args)
                prop = manager.props_library.get(prop_name, GOLD)
                n = default_bet
                bank = prop.locate_bank(user, account)
                if n > bank[prop.id]:
                    return f"你没有足够的{prop.name}支撑这场对决({bank[prop.id]})。"
                session = place[group_id] = Session(group_id, user_id, account.name or user.name)
                if event.at:
                    session.at = event.at[0]
                    session.p2_nickname = manager.locate_account(session.at, group_id)[1].name
                if n:
                    session.bet = (prop, n)
                session.round = 1
                return await func(session, arg)

            return wrapper

        return decorator

    def action(self, place: dict[str, Session]):
        def decorator(func: Callable[[Session, str], Coroutine]):
            async def wrapper(event: Event):
                user, account = manager.account(event)
                group_id = account.group_id
                user.connect = group_id
                user_id = user.id
                if (session := place.get(group_id)) and (tip := session.create_check(user_id)):
                    return tip
                prop_name, n, arg = self.args_parse(event.args)
                prop = manager.props_library.get(prop_name, GOLD)
                n = default_bet
                bank = prop.locate_bank(user, account)
                if n > bank[prop.id]:
                    return f"你没有足够的{prop.name}支撑这场对决({bank[prop.id]})。"
                session = place[group_id] = Session(group_id, user_id, account.name or user.name)
                if event.at:
                    session.at = event.at[0]
                    session.p2_nickname = manager.locate_account(session.at, group_id)[1].name
                if n:
                    session.bet = (prop, n)
                session.round = 1
                return await func(session, arg)

            return wrapper

        return decorator
