import random


def random_poker(n: int = 1, range_point: tuple[int, int] = (1, 14)):
    """
    生成随机牌库
    """
    poker_deck = [(suit, point) for suit in range(1, 5) for point in range(*range_point)]
    poker_deck = poker_deck * n
    random.shuffle(poker_deck)
    return poker_deck


poker_suit = {4: "♠", 3: "♥", 2: "♣", 1: "♦"}
poker_point = {
    1: " A",
    2: " 2",
    3: " 3",
    4: " 4",
    5: " 5",
    6: " 6",
    7: " 7",
    8: " 8",
    9: " 9",
    10: "10",
    11: " J",
    12: " Q",
    13: " K",
    14: " A",
}


def poker_show(hand: list[tuple[int, int]], split: str = ""):
    return split.join(f"【{poker_suit[suit]}{poker_point[point]}】" for suit, point in hand)
