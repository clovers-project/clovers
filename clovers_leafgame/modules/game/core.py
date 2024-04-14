import time
import asyncio
from collections import Counter
from collections.abc import Coroutine, Callable, Sequence
from clovers.utils.tools import to_int
from clovers_leafgame.main import manager
from clovers_leafgame.item import Prop, GOLD
from clovers_leafgame.output import text_to_image, endline
from clovers_leafgame.core.clovers import Event
from clovers.core.config import config as clovers_config
from .config import Config

config_key = __package__
config_data = Config.parse_obj(clovers_config.get(config_key, {}))
clovers_config[config_key] = config_data.dict()

default_bet = config_data.default_bet
timeout = config_data.timeout


class Session:
    """
    游戏场次信息
    """

    time: float
    group_id: str
    at: str | None = None
    p1_uid: str
    p1_nickname: str
    p2_uid: str = ""
    p2_nickname: str | None = None
    round = 1
    next: str
    win: str | None = None
    bet: tuple[Prop, int] | None = None
    data: dict = {}
    game: "Game"
    end_tips: str | None = None
    start_tips: ... = None

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

    def double_bet(self):
        if not self.bet:
            return
        prop, n = self.bet
        n += self.data["bet"]
        self.bet = (prop, min(n, self.data["bet_limit"]))

    def delay(self, t: float = 0):
        self.time = time.time() + t

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

    def settle(self):
        """
        游戏结束结算
            return:结算界面
        """
        group_id = self.group_id
        win = self.win if self.win else self.p1_uid if self.next == self.p2_uid else self.p2_uid
        if win == self.p1_uid:
            win_name = self.p1_nickname
            lose = self.p2_uid
            lose_name = self.p2_nickname
        else:
            win_name = self.p2_nickname
            lose = self.p1_uid
            lose_name = self.p1_nickname

        bet = self.bet
        if bet:
            tip = manager.transfer(*bet, lose, win, group_id)
            info = [text_to_image(tip + endline("结算"), autowrap=True)]
        else:
            info = []
        ranklist = manager.data.extra.setdefault("ranklist", {})
        win_rank = ranklist["win"] = Counter(ranklist.get("win", {}))
        win_rank[win] += 1
        lose_rank = ranklist["lose"] = Counter(ranklist.get("lose", {}))
        lose_rank[lose] += 1
        win_achieve = ranklist["win_achieve"] = Counter(ranklist.get("win_achieve", {}))
        win_achieve[win] += 1
        win_achieve[lose] = 0
        lose_achieve = ranklist["lose_achieve"] = Counter(ranklist.get("lose_achieve", {}))
        lose_achieve[win] = 0
        lose_achieve[lose] += 1
        card = (
            f"[pixel][20]◆胜者 {win_name}[nowrap]\n[pixel][460]◇败者 {lose_name}\n"
            f"[pixel][20]◆战绩 {win_rank[win]}:{lose_rank[win]}[nowrap]\n[pixel][460]◇战绩 {win_rank[lose]}:{lose_rank[lose]}\n"
            f"[pixel][20]◆连胜 {win_achieve[win]}[nowrap]\n[pixel][460]◇连败 {lose_achieve[lose]}"
        )
        info.insert(0, text_to_image(card + endline("对战")))
        result = [f"这场对决是 {win_name} 胜利了", manager.info_card(info, win)]
        if self.end_tips:
            result.append(self.end_tips)
        return result

    def end(self, result=None):
        self.time = 0
        settle = self.settle()

        async def output():
            if result:
                yield result
                await asyncio.sleep(1)
            for x in settle:
                yield x
                await asyncio.sleep(1)

        return output()


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
                user.connect = group_id
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
                group_id = event.group_id or manager.data.user(event.user_id).connect
                if not (session := self.session_check(place, group_id)):
                    return
                if session.game.name != self.name:
                    return
                user_id = event.user_id
                if tip := session.action_check(user_id):
                    return tip
                return await func(event, session)

            return wrapper

        return decorator
