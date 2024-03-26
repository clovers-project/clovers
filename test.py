import random


def random_poker(n: int = 1):
    """
    生成随机牌库
    """
    poker_deck = [(i, j) for i in range(1, 5) for j in range(1, 14)]
    poker_deck = poker_deck * n
    random.shuffle(poker_deck)
    return poker_deck


poker_suit = {4: "♠", 3: "♥", 2: "♣", 1: "♦"}
poker_point = {1: "2", 2: "3", 3: "4", 4: "5", 5: "6", 6: "7", 7: "8", 8: "9", 9: "10", 10: "J", 11: "Q", 12: "K", 13: "A"}


def cantrell_pt(hand: list[tuple[int, int]]):
    """
    牌型点数
    """
    pt = 0
    name = []
    print(type(suits), suits)
    # 判断同花
    if len(set(suits)) == 1:
        pt += suits[0]
        if is_straight(points):
            point = max(points)
            pt += point * (100**9)
            name.append(f"同花顺{poker_suit[suits[0]]} {poker_point[point]}")
        else:
            point = sum(points)
            pt += point * (100**6)
            name.append(f"同花{poker_suit[suits[0]]} {point}")
    else:
        pt += sum(suits)
        # 判断顺子
        if is_straight(points):
            point = max(points)
            pt += point * (100**5)
            name.append(f"顺子 {poker_point[point]}")
        else:
            setpoints = set(points)
            # 判断四条或葫芦
            if len(setpoints) == 2:
                for point in setpoints:
                    if points.count(point) == 4:
                        pt += point * (100**8)
                        name.append(f"四条 {poker_point[point]}")
                    if points.count(point) == 3:
                        pt += point * (100**7)
                        name.append(f"葫芦 {poker_point[point]}")
            else:
                # 判断三条，两对，一对
                exp = 1
                tmp = 0
                for point in setpoints:
                    if points.count(point) == 3:
                        pt += point * (100**4)
                        name.append(f"三条 {poker_point[point]}")
                        break
                    if points.count(point) == 2:
                        exp += 1
                        tmp += point
                        name.append(f"对 {poker_point[point]}")
                else:
                    pt += tmp * (100**exp)

            tmp = 0
            for point in setpoints:
                if points.count(point) == 1:
                    pt += point * (100)
                    tmp += point
            if tmp:
                name.append(f"散 {tmp}")

    return pt, " ".join(name)


def is_straight(points: list[int]):
    """
    判断是否为顺子
    """
    points = sorted(points)
    for i in range(1, len(points)):
        if points[i] - points[i - 1] != 1:
            return False
    return True


deck = random_poker()[:5]
print([(poker_suit[suit], poker_point[point]) for suit, point in deck])
print(cantrell_pt(deck))
print({suit + 1: point for suit, point in poker_point.items()})
