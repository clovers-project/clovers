import random


def random_poker(n: int = 1):
    """
    生成随机牌库
    """
    poker_deck = [(i, j) for i in range(1, 5) for j in range(1, 14)]
    poker_deck = poker_deck * n
    random.shuffle(poker_deck)
    return poker_deck
