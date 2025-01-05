from collections.abc import Callable, Coroutine

type Method = Callable[..., Coroutine]
type MethodLib = dict[str, Method]
type Task = Callable[[], Coroutine]
