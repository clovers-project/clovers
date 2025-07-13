from types import UnionType
from typing import get_origin, get_args, Union, Any, TypeVar, TypedDict
from collections.abc import Callable, Generator, AsyncGenerator, Iterable


class CloversProtocol(TypedDict):
    properties: dict[str, Any] | None
    sends: dict[str, Any] | None
    calls: dict[str, Any] | None


def check_compatible(type_A: Any, type_B: Any) -> bool:
    """检查 A 是否是 B 的兼容类型

    判断逻辑:

        属性: A 的范围小于或等于 B 的范围。
        方法: A 的参数范围大于等于 B 的参数范围，A 的返回值范围小于或等于 B 的返回值范围。

    Args:
        type_A (Any): A
        type_B (Any): B
        recursion (bool): 是否在递归内

    Returns:
        bool: A 是 B 的兼容类型
    """

    def _is_union(type: Any):
        return type in (Union, UnionType)

    def _subclass(type_A: Any, type_B: Any) -> bool:
        try:
            return issubclass(type_A, type_B)
        except TypeError:
            pass
        if args_B := get_args(type_B):
            return type_A is args_B[0] and issubclass(type_A, Iterable) and _subclass(type_A, get_origin(type_B))
        else:
            return False

    def _structural_subtype(type_A: Any, type_B: Any) -> bool:
        """判断 A 是否在结构上被 B 兼容

        判断逻辑:

            B 拥有 A 的 全部属性，而且 B 的同名属性能被 A 赋值
        """
        if (fields_A := getattr(type_A, "__annotations__", None)) is None:
            return False
        if (fields_B := getattr(type_B, "__annotations__", None)) is None:
            return False
        keys = set(fields_A.keys())
        if keys.difference(fields_B.keys()):
            return False
        return all(check_compatible(fields_A[key], fields_B[key]) for key in keys)

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
    if isinstance(type_A, type):
        return _subclass(type_A, type_B) or _structural_subtype(type_A, type_B)
    origin_A = get_origin(type_A)
    origin_B = get_origin(type_B)
    args_A = get_args(type_A)
    args_B = get_args(type_B)
    # print(type_A, type(type_A), origin_A, args_A)
    # print(type_B, type(type_B), origin_B, args_B)
    # 联合类型
    if _is_union(origin_A):
        if _is_union(origin_B):
            return all(any(check_compatible(arg_A, arg_B) for arg_B in args_B) for arg_A in args_A)
        else:
            return all(check_compatible(arg_A, type_B) for arg_A in args_A)
    elif _is_union(origin_B):
        return any(check_compatible(type_A, arg_B) for arg_B in args_B)
    # 普通类型
    elif origin_A is origin_B:
        # 基本类型
        if origin_A is None:
            return check_compatible(type_A, type_B)
        # 同构造泛型类型
        elif origin_A is Callable:  # 函数类型必须用 collections.abc.Callable 标注
            param_A, retuen_A = args_A
            param_B, return_B = args_B
            # 对函数类型的参数进行反向兼容检查
            # if isinstance(param_A, EllipsisType):
            if param_A is ...:
                return check_compatible(retuen_A, return_B)
            # if isinstance(param_B, EllipsisType):
            if param_B is ...:
                return False
            return all(_subclass(*args) for args in zip(param_B, param_A)) and check_compatible(retuen_A, return_B)
        # 对函数生成器只检查生成类型
        elif origin_A in (Generator, AsyncGenerator):
            return check_compatible(args_A[0], args_B[0])
        # 构造函数的参数兼容
        else:
            return len(args_A) == len(args_B) and all(check_compatible(*args) for args in zip(args_A, args_B))
    # 同构造继承泛型
    if _subclass(origin_A, origin_B):
        if origin_A is tuple:
            # if isinstance(args_A[-1], EllipsisType):
            if args_A[-1] is ...:
                return len(args_A) - 1 == len(args_B) and check_compatible(args_A[0], args_B[0])
            return False
        else:
            return len(args_A) == len(args_B) and all(check_compatible(*args) for args in zip(args_A, args_B))
    # 其他视为不兼容
    return False
