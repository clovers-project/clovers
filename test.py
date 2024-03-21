import random
from collections.abc import Callable


def func_1(Name, Age):
    print("func_1 called")
    print("Name:", Name)
    print("Age:", Age)


def func_2(Age, Sex):
    print("func_2 called")
    print("Age:", Age)
    print("Sex:", Sex)


func_list: list[Callable] = [func_1, func_2]


def func(**kwargs):
    now_func = random.choice(func_list)
    now_func_args = set(now_func.__code__.co_varnames)
    return random.choice([func_1, func_2])(**{k: v for k, v in kwargs.items() if k in now_func_args})


result = func(Name="Joah", Age=10, Sex="man")
