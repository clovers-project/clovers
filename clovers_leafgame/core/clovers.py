from collections.abc import Callable, Coroutine
from clovers_core.plugin import Event as CloversEvent
from clovers_core.utils import kwfilter
from clovers_utils.tools import to_int


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
    def at(self) -> list:
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

    def decorator(self, func: Callable[..., Coroutine]):
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
            check = lambda event: any(check(event) for check in self.check)
        wrapper = kwfilter(func)

        async def checker(event: Event):
            if not check(event):
                return
            return await wrapper(event)

        return checker


to_me = Check(to_me=True)
superuser = Check(superuser=True)
group_admin = Check(group_admin=True)
at_list = Check(at=True)
