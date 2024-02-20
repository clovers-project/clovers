from io import BytesIO
from collections.abc import Callable, Coroutine
from clovers_core.plugin import Plugin, Result
from .core.clovers import Event


def build_result(result) -> Result:
    if isinstance(result, str):
        return Result("text", result)
    if isinstance(result, BytesIO):
        return Result("image", result)
    return result


plugin = Plugin(
    build_event=lambda e: Event(e),
    build_result=build_result,
)


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
