import time
from collections.abc import Coroutine, Callable

from clovers_core.plugin import Plugin, Event, Result

timeout = 60


class LiteGameException(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class Session:
    def __init__(self) -> None:
        self.update_time()
        self.name: str = None
        self.alias: str = None
        self.data: dict = {}

    @property
    def timeout(self):
        return time.time() - self.time - timeout

    def update_time(self):
        self.time = time.time()


class Game:
    def __init__(self, alias: str) -> None:
        self.alias: str = alias


class Manager:
    def __init__(self) -> None:
        self.place: dict[str, Session] = {}
        self.games: dict[str, Game] = {}

    def create_session(self, id: str):
        session = self.place.get(id)
        if session is None or session.timeout > 0:
            self.place[id] = Session()
            return True, self.place[id]
        return False, session

    def get_session(self, id: str):
        return self.place.get(id)

    def game_init(self, name: str, alias: str):
        if name in self.games:
            raise LiteGameException(f"游戏名：{name} 已被注册")
        self.games[name] = Game(alias=alias)

    def game_create(self, name: str, create_tips: str):
        if not name in self.games:
            raise LiteGameException(f"游戏名：{name} 未注册")
        game = self.games[name]

        def decorator(func: Callable):
            async def wrapper(event: Event) -> Result:
                flag, session = self.create_session(event.kwargs["group_id"])
                if not flag:
                    msg = f"游戏：{session.alias}正在进行中。还有{-int(session.timeout)}s超时。"
                    return Result("text", msg)
                session.name = name
                session.alias = game.alias
                session.data = func()
                return Result("text", create_tips)

            return wrapper

        return decorator

    def game_playing(self, name: str):
        if not name in self.games:
            raise LiteGameException(f"游戏名：{name} 未注册")

        def decorator(func: Coroutine):
            async def wrapper(event: Event) -> Result:
                session = self.place.get(event.kwargs["group_id"])
                if not session:
                    return
                if session.name != name:
                    return
                session.update_time()
                text = await func(session, event)
                if text:
                    return Result("text", text)

            return wrapper

        return decorator
