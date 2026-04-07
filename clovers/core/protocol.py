from functools import lru_cache
from types import UnionType
from typing import get_origin, get_args, get_overloads, Union, Any, TypeVar, Literal, TypeAliasType, Optional, TypedDict
from collections.abc import Callable, Generator, AsyncGenerator
from ..base import Coro
from ..logger import logger


def _is_union(type: Any):
    return type in (Union, UnionType)


def _is_subclass(type_A: Any, type_B: Any, origin_B: Any) -> bool:
    if _is_union(origin_B):
        return any(_is_subclass(type_A, arg_B, get_origin(arg_B)) for arg_B in get_args(type_B))
    return issubclass(type_A, type_B)
    # try:
    #     return issubclass(type_A, type_B)
    # except TypeError:
    #     pass
    # if args_B := get_args(type_B):
    #     return type_A is args_B[0] and issubclass(type_A, Iterable) and _subclass(type_A, get_origin(type_B))
    # else:
    #     return False


def _structural_subtype(type_A: Any, type_B: Any, origin_B: Any) -> bool:
    """判断 A 是否在结构上被 B 兼容

    判断逻辑:

        B 拥有 A 的 全部属性，而且 B 的同名属性能被 A 赋值
    """
    if _is_union(origin_B):
        return any(_structural_subtype(type_A, arg_B, get_origin(arg_B)) for arg_B in get_args(type_B))
    if (fields_A := getattr(type_A, "__annotations__", None)) is None:
        return False
    if (fields_B := getattr(type_B, "__annotations__", None)) is None:
        return False
    keys = set(fields_A.keys())
    if keys.difference(fields_B.keys()):
        return False
    return all(check_compatible(fields_A[key], fields_B[key]) for key in keys)


def _flatten_type(T: Any) -> Any:
    if isinstance(T, TypeAliasType):
        T = T.__value__
    origin = get_origin(T)
    if isinstance(origin, TypeAliasType):
        T = origin.__value__[get_args(T)]
        origin = get_origin(T)
    if origin is Optional:
        T = Union[get_args(T)]  # get_args(Optional[T]) == (T, type(None))
        origin = Union
    return T, origin


def _literal_check(literal_args: tuple, check_T: Any, check_origin: Any) -> bool:
    if literal_args is ...:
        return False
    if check_origin is Literal:
        check_args = get_args(check_T)
        return all(any((literal == check_arg) for check_arg in check_args) for literal in literal_args)
    if _is_union(check_origin):
        check_args = get_args(check_T)
        return any(_literal_check(literal_args, check_arg, get_origin(check_arg)) for check_arg in check_args)
    return all(isinstance(check_arg, check_T) for check_arg in literal_args)


def _union_check_all(union_args: Any, check_T: Any, check_origin: Any) -> bool:
    if _is_union(check_origin):
        check_args = get_args(check_T)
        return all(any(check_compatible(union_arg, check_arg) for check_arg in check_args) for union_arg in union_args)
    else:
        return all(check_compatible(union_arg, check_T) for union_arg in union_args)


def _function_check(func_A: Callable, func_B: Callable) -> bool:
    args_A = get_args(func_A)
    if len(args_A) != 2:
        return True
    args_B = get_args(func_B)
    if len(args_B) != 2:
        return False
    param_A, retuen_A = args_A
    param_B, return_B = args_B
    if param_A is ...:
        return check_compatible(retuen_A, return_B)
    if param_B is ...:
        return False
    if len(param_A) != len(param_B):
        return False
    if not check_compatible(retuen_A, return_B):
        return False
    return all(check_compatible(*args) for args in zip(param_B, param_A))


def _generator_check(generator_A: Generator, generator_B: Generator) -> bool:
    args_A = get_args(generator_A)
    if not args_A:
        return True
    args_B = get_args(generator_B)
    if not args_B:
        return False
    return check_compatible(args_A[0], args_B[0])


def _same_check[T: Any](type_A: T, type_B: T) -> bool:
    args_A = get_args(type_A)
    if not args_A:
        return True
    args_B = get_args(type_B)
    if not args_B:
        return False
    if len(args_A) != len(args_B):
        return False
    return all(check_compatible(*args) for args in zip(args_A, args_B))


def _subclass_check(type_A: Any, origin_A: Any, type_B: Any) -> bool:
    args_A = get_args(type_A)
    args_B = get_args(type_B)
    if not args_A:
        if origin_A is str:
            return len(args_B) > 0 and (args_B[0] is str)
        elif origin_A in (bytes, bytearray, memoryview):
            return len(args_B) > 0 and (args_B[0] is bytes)
        else:
            return len(args_B) == 0
    if not args_B:
        return False
    if len(args_B) != 1:
        return False
    item_A = args_A[0]
    item_B = args_B[0]
    if origin_A is tuple:
        l_args_A = len(args_A)
        if (l_args_A == 1) or ((l_args_A == 2) and (args_A[1] is ...)):
            return check_compatible(item_A, item_B)
        return False
    if len(args_A) != 1:
        return False
    return check_compatible(item_A, item_B)


@lru_cache(maxsize=128)
def check_compatible(type_A: Any, type_B: Any) -> bool:
    """检查 A 是否是 B 的兼容类型

    判断逻辑:

        属性: A 的范围小于或等于 B 的范围。
        方法: A 的参数范围大于等于 B 的参数范围，A 的返回值范围小于或等于 B 的返回值范围。

    Args:
        type_A (Any): A
        type_B (Any): B

    Returns:
        bool: A 是 B 的兼容类型
    """
    if type_B is type_A:
        return True
    # if isinstance(type_B, EllipsisType):
    if type_B is ...:
        return True
    # if isinstance(type_A, EllipsisType):
    if type_A is ...:
        return False
    if type_B is Any:
        return True
    if type_A is Any:
        return False
    if isinstance(type_B, TypeVar) and (type_B := type_B.__bound__) is None:
        return True
    if isinstance(type_A, TypeVar) and (type_A := type_A.__bound__) is None:
        return False
    type_A, origin_A = _flatten_type(type_A)
    type_B, origin_B = _flatten_type(type_B)
    if isinstance(type_A, type):
        return _is_subclass(type_A, type_B, origin_B) or _structural_subtype(type_A, type_B, origin_B)
    # print(type_A, type(type_A), origin_A, args_A)
    # print(type_B, type(type_B), origin_B, args_B)
    # print(f"{type_A = }\n{origin_A = }\n{type_B = }\n{origin_B = }")
    if origin_A is Literal:
        return _literal_check(get_args(type_A), type_B, origin_B)
    # 联合类型
    elif _is_union(origin_A):
        return _union_check_all(get_args(type_A), type_B, origin_B)
    elif _is_union(origin_B):
        return any(check_compatible(type_A, arg_B) for arg_B in get_args(type_B))
    # 普通类型
    elif origin_A is origin_B:
        # 基本类型
        if origin_A is None:
            return check_compatible(type_A, type_B)
        # 同构造泛型类型
        elif origin_A is Callable:  # 函数类型必须用 collections.abc.Callable 标注
            return _function_check(type_A, type_B)
        # 对函数生成器只检查生成类型
        elif origin_A in (Generator, AsyncGenerator):
            return _generator_check(type_A, type_B)
        # 构造函数的参数兼容
        else:
            return _same_check(type_A, type_B)
    # 同构造继承泛型
    elif _is_subclass(origin_A, origin_B, get_origin(origin_B)):
        return _subclass_check(type_A, origin_A, type_B)
    # 其他视为不兼容
    return False


def literal_arg(literal: type):
    origin = get_origin(literal)
    if not origin is Literal:
        return
    if not (args := get_args(literal)):
        return
    return args


def is_coro(func: Callable):
    return func.__code__.co_flags & 0x0080


class TypeProtocol:
    """类型协议

    Attributes:
        send (dict[str, type]]): 发送参数类型协议
        call (dict[str, type]]): 调用额外参数与返回值类型协议
    """

    class __Protocol(TypedDict):
        call: dict[str, Any]
        send: dict[str, Any]

    def __init__(self) -> None:
        self.__protocol: TypeProtocol.__Protocol = {"send": {}, "call": {}}

    @property
    def send(self):
        return self.__protocol["send"]

    @property
    def call(self):
        return self.__protocol["call"]

    def __bool__(self):
        return bool(self.__protocol["send"]) or bool(self.__protocol["call"])

    @staticmethod
    def protocol_format(protocol: type) -> __Protocol:
        calls = {k: v for k, v in protocol.__annotations__.items() if not k.startswith("_")}
        sends = {}
        attr = getattr(protocol, "call", None)
        if attr is not None:
            for func in get_overloads(attr):
                varnames = func.__code__.co_varnames
                fields = func.__annotations__
                if "return" not in fields:
                    continue
                len_varnames = len(varnames)
                if len_varnames < 2:
                    continue
                elif len_varnames == 2:
                    if (literal_args := literal_arg(fields[varnames[1]])) is None:
                        continue
                    calls[literal_args[0]] = fields["return"]
                    continue
                _, key_name, *names = varnames
                if (literal_args := literal_arg(fields[key_name])) is None:
                    continue
                if not all(name in fields for name in names):
                    continue
                if is_coro(func):
                    calls[literal_args[0]] = Callable[[fields[name] for name in names], Coro[fields["return"]]]
                else:
                    calls[literal_args[0]] = Callable[[fields[name] for name in names], fields["return"]]
        attr = getattr(protocol, "send", None)
        if attr is not None:
            for func in get_overloads(attr):
                varnames = func.__code__.co_varnames
                fields = func.__annotations__
                if not len(varnames) == 3:
                    continue
                _, key_name, message_name = varnames
                if (literal_args := literal_arg(fields[key_name])) is None:
                    continue
                sends[literal_args[0]] = fields[message_name]
        return {"call": calls, "send": sends}

    def check(self, protocol: type | None):
        """检查适配器类型协议

        Args:
            data (type): 事件协议类型，包含字段和声明的类型
        """
        if protocol is None:
            return True
        check_protocol = self.protocol_format(protocol)
        for k in ["send", "call"]:
            if (self_fields := self.__protocol[k]) and (check_fields := check_protocol[k]):
                keys = check_fields.keys() & self_fields.keys()
                for key in keys:
                    if not check_compatible(self_fields[key], check_fields[key]):
                        logger.warning(f'{k}[{key}] provides type "{self_fields[key]}", but protocol require "{check_fields[key]}".')
                        return False
        return True

    def register_send(self, key: str, send: Callable):
        name = send.__code__.co_varnames[0]
        if annot := send.__annotations__.get(name):
            self.__protocol["send"][key] = annot

    def register_call(self, key: str, call: Callable):
        co_posonlyargcount = call.__code__.co_posonlyargcount
        if co_posonlyargcount == 0:
            if annot := call.__annotations__.get("return"):
                self.__protocol["call"][key] = annot
        else:
            names = call.__code__.co_varnames[:co_posonlyargcount]
            fields = call.__annotations__
            if all(name in fields for name in names) and "return" in fields:
                if is_coro(call):
                    self.__protocol["call"][key] = Callable[[fields[name] for name in names], Coro[fields["return"]]]
                else:
                    self.__protocol["call"][key] = Callable[[fields[name] for name in names], fields["return"]]
