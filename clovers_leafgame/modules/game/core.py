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
    round = 1
    next: str | None = None
    win: str | None = None
    bet: tuple[Prop, int] | None = None
    data: dict = {}
    game: "Game"

    def __init__(self, group_id: str, user_id: str, nickname: str, game: "Game"):
        self.time = time.time()
        self.group_id = group_id
        self.p1_uid = user_id
        self.p1_nickname = nickname
        self.next = user_id
        self.game = game

    def join(self, user_id: str, nickname: str):
        self.time = time.time()
        self.p2_uid = user_id
        self.p2_nickname = nickname

    def timeout(self):
        return timeout + self.time - time.time()

    def nextround(self):
        self.time = time.time()
        self.round += 1
        self.next = self.p1_uid if self.next == self.p2_uid else self.p2_uid

    def create_check(self, user_id: str):
        p2_uid = self.p2_uid
        if not p2_uid:
            return
        p1_uid = self.p1_uid
        if p1_uid == user_id:
            return "你已发起了一场对决"
        if p2_uid == user_id:
            return "你正在进行一场对决"
        if p1_uid and p2_uid:
            return f"{self.p1_nickname} 与 {self.p2_nickname} 的对决还未结束，请等待比赛结束后再开始下一轮..."

    def action_check(self, user_id: str):
        if not self.p2_uid:
            if self.p1_uid == user_id:
                return "目前无人接受挑战哦"
            return "请先接受挑战"
        if self.p1_uid == user_id or self.p2_uid == user_id:
            if user_id == self.next:
                return
            return f"现在是{self.p1_nickname if self.next == self.p1_uid else self.p2_nickname}的回合"
        return f"{self.p1_nickname} v.s. {self.p2_nickname}\n正在进行中..."

    def create_info(self):
        if self.at:
            p2_nickname = self.p2_nickname or f"玩家{self.at[:4]}..."
            return f"{self.p1_nickname} 向 {p2_nickname} 发起挑战！\n请 {p2_nickname} 回复 接受挑战 or 拒绝挑战\n【{timeout}秒内有效】"
        else:
            return f"{self.p1_nickname} 发起挑战！\n回复 接受挑战 即可开始对局。\n【{timeout}秒内有效】"

    def end(self, result=None): ...


class Game:
    def __init__(self, name: str, action_tip: str) -> None:
        self.name = name
        self.action_tip = action_tip

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

    @staticmethod
    def session_check(place: dict[str, Session], group_id: str):
        if not (session := place.get(group_id)):
            return
        if session.timeout() < 0:
            del place[group_id]
            return
        return session

    def create(self, place: dict[str, Session]):
        def decorator(func: Callable[[Session, str], Coroutine]):
            async def wrapper(event: Event):
                user_id = event.user_id
                group_id = event.group_id
                if (session := self.session_check(place, user_id)) and (tip := session.create_check(user_id)):
                    return tip
                prop_name, n, arg = self.args_parse(event.args)
                prop = manager.props_library.get(prop_name, GOLD)
                user, account = manager.locate_account(user_id, group_id)
                bank = prop.locate_bank(user, account)
                if n < 0:
                    n = default_bet
                if n > bank[prop.id]:
                    return f"你没有足够的{prop.name}支撑这场对决({bank[prop.id]})。"
                session = place[group_id] = Session(group_id, user_id, account.name or user.name, game=self)
                if event.at:
                    session.at = event.at[0]
                    session.p2_nickname = manager.locate_account(session.at, group_id)[1].name
                if n:
                    session.bet = (prop, n)
                return await func(session, arg)

            return wrapper

        return decorator

    def action(self, place: dict[str, Session]):
        def decorator(func: Callable[[Event, Session], Coroutine]):
            async def wrapper(event: Event):
                group_id = event.group_id
                if not (session := self.session_check(place, group_id)):
                    return
                user_id = event.user_id
                if tip := session.action_check(user_id):
                    return tip
                return await func(event, session)

            return wrapper

        return decorator
