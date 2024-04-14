from collections.abc import Callable, Coroutine
from clovers.core.plugin import Event as CloversEvent
from clovers.utils.tools import to_int


class Event:
    def __init__(self, event: CloversEvent):
        self.event: CloversEvent = event

    @property
    def raw_command(self):
        return self.event.raw_command

    @property
    def args(self):
        return self.event.args

    @property
    def user_id(self) -> str:
        return self.event.kwargs["user_id"]

    @property
    def group_id(self) -> str:
        return self.event.kwargs["group_id"]

    @property
    def nickname(self) -> str:
        return self.event.kwargs["nickname"]

    @property
    def permission(self) -> int:
        return self.event.kwargs["permission"]

    @property
    def to_me(self) -> bool:
        return self.event.kwargs["to_me"]

    @property
    def at(self) -> list[str]:
        return self.event.kwargs["at"]

    def is_private(self) -> bool:
        return self.group_id is None

    @property
    def avatar(self) -> str:
        return self.event.kwargs["avatar"]

    @property
    def image_list(self) -> list[str]:
        return self.event.kwargs["image_list"]

    @property
    def group_avatar(self) -> str:
        return self.event.kwargs["group_avatar"]

    @property
    def group_info(self) -> list:
        return self.event.kwargs["group_info"]

    def args_to_int(self):
        if args := self.args:
            n = to_int(args[0]) or 0
        else:
            n = 0
        return n

    def args_parse(self) -> tuple[str, int, float] | None:
        args = self.args
        if not args:
            return
        l = len(args)
        if l == 1:
            return args[0], 1, 0
        name = args[0]
        n = args[1]
        if number := to_int(n):
            n = number
        elif number := to_int(name):
            name = n
            n = number
        else:
            n = 1
        f = 0
        if l > 2:
            try:
                f = float(args[2])
            except:
                pass
        return name, n, f

    def single_arg(self):
        if args := self.args:
            return args[0]

    async def send_group_message(self, group_id: str, result):
        func = self.event.kwargs.get("send_group_message")
        if not func:
            return
        try:
            await func(group_id=group_id, result=result)
        except Exception as e:
            print(e)


class Check:
    checker: list[Callable[[Event], bool]]

    def __init__(self) -> None:
        self.checker = []

    def superuser(self):
        self.checker.append(lambda event: event.permission > 2)
        return self

    def group_owner(self):
        self.checker.append(lambda event: event.permission > 1)
        return self

    def group_admin(self):
        self.checker.append(lambda event: event.permission > 0)
        return self

    def locate(self, user_id, group_id):
        self.checker.append(lambda event: event.user_id == user_id or event.group_id == group_id)
        return self

    def to_me(self):
        self.checker.append(lambda event: event.to_me)
        return self

    def at(self):
        self.checker.append(lambda event: bool(event.at))
        return self

    def check(self, func: Callable[..., Coroutine]) -> Callable[..., Coroutine]:
        if len(self.checker) == 1:
            checker = self.checker[0]
        else:
            checker = lambda event: any(checker(event) for checker in self.checker)

        if "event" in func.__code__.co_varnames:

            async def wrapper(event: Event, *args, **kwargs):
                if checker(event):
                    return await func(event, *args, **kwargs)

            return wrapper
        else:

            async def wrapper(event: Event, *args, **kwargs):
                if checker(event):
                    return await func(*args, **kwargs)

            return wrapper
