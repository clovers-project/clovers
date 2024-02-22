from collections.abc import Callable, Coroutine
from clovers_core.plugin import Event as CloversEvent
from .utils import to_int


class Event:
    def __init__(self, raw_event: CloversEvent):
        self.raw_event: CloversEvent = raw_event

    @property
    def user_id(self) -> str:
        return self.raw_event.kwargs["user_id"]

    @property
    def group_id(self) -> str:
        return self.raw_event.kwargs["group_id"]

    @property
    def nickname(self) -> str:
        return self.raw_event.kwargs["nickname"]

    @property
    def permission(self) -> int:
        return self.raw_event.kwargs["permission"]

    @property
    def to_me(self) -> bool:
        return self.raw_event.kwargs["to_me"]

    @property
    def at(self) -> list:
        return self.raw_event.kwargs["at"]

    def is_private(self) -> bool:
        return self.group_id is None

    @property
    def avatar(self) -> str:
        return self.raw_event.kwargs["avatar"]

    @property
    def group_info(self) -> list:
        return self.raw_event.kwargs["group_info"]

    def args_to_int(self):
        return to_int(self.raw_event.args[0])

    def args_parse(self):
        args = self.raw_event.args
        if not args:
            return
        L = len(args)
        if L == 1:
            return args[0], 1, None
        name = args[0]
        N = args[1]
        if number := to_int(N):
            N = number
        elif number := to_int(N):
            name = N
            N = number
        else:
            N = 1
        limit = None
        if L > 2:
            try:
                limit = float(args[2])
            except:
                pass
        return name, N, limit

    def single_arg(self):
        if args := self.raw_event.args:
            return args[0]


class Check:
    superuser: bool = False
    group_owner: bool = False
    group_admin: bool = False
    to_me: bool = False
    at: bool = False

    def __init__(
        self,
        superuser: bool = False,
        group_owner: bool = False,
        group_admin: bool = False,
        to_me: bool = False,
        at: bool = False,
    ) -> None:
        self.superuser: bool = superuser
        self.group_owner: bool = group_owner
        self.group_admin: bool = group_admin
        self.to_me: bool = to_me
        self.at: bool = at
        self.check: list[Callable[[Event], bool]] = []

    def wrapper(self, func: Callable[[Event], Coroutine]):
        if self.superuser:
            self.check.append(lambda event: event.permission > 2)
        elif self.group_owner:
            self.check.append(lambda event: event.permission > 1)
        elif self.group_admin:
            self.check.append(lambda event: event.permission > 0)
        if self.to_me:
            self.check.append(lambda event: event.to_me)
        if self.at:
            self.check.append(lambda event: True if event.at else False)

        if len(self.check) == 1:
            check = self.check[0]
        else:

            def check_all(event: Event):
                for check in self.check:
                    if not check(event):
                        return False
                return True

            check = check_all

        async def decorator(event: Event):
            if not check(event):
                return
            return await func(event)

        return decorator


to_me = Check(to_me=True)
superuser = Check(superuser=True)
group_admin = Check(group_admin=True)
at = Check(at=True)
