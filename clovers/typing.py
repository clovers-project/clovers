from collections.abc import Callable, Coroutine, Awaitable

type Method = Callable[..., Coroutine]
type MethodLib = dict[str, Method]
type Task = Callable[[], Coroutine]
type RunningTask = Awaitable
