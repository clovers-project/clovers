import random
import asyncio
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.core.clovers import Event
from clovers_leafgame.output import text_to_image, BytesIO
from .core import Session, Game, to_int
from .tools import random_poker, poker_suit, poker_point
from clovers_core.config import config as clovers_config
from .config import Config

config = Config.parse_obj(clovers_config.get(__package__, {}))

place: dict[str, Session] = {}


@plugin.handle({"接受挑战"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    group_id = event.group_id
    session = Game.session_check(place, group_id)
    if not session:
        return
    user_id = event.user_id
    if session.p2_uid or session.p1_uid == user_id:
        return
    if session.at and session.at != user_id:
        return f"现在是 {session.p1_nickname} 发起的对决，请等待比赛结束后再开始下一轮..."
    user, group_account = manager.locate_account(user_id, group_id)
    user.connect = group_id
    bet = session.bet
    if bet:
        prop, n = bet
        if group_account.bank[prop.id] < n:
            return f"你的无法接受这场对决！\n——你还有{group_account.bank[prop.id]}个{prop.name}。"
        tip = f"对战金额为 {n} {prop.name}\n"
    else:
        tip = ""
    session.join(user_id, event.nickname)
    session.next = session.p1_uid
    return f"{session.p2_nickname}接受了对决！\n本场对决为【{session.game.name}】\n{tip}请{session.p1_nickname}发送指令\n{session.game.action_tip}"


@plugin.handle({"拒绝挑战"}, {"user_id", "group_id"})
async def _(event: Event):
    session = Game.session_check(place, event.group_id)
    if session and (at := session.at) and at == event.user_id:
        if session.p2_uid:
            return "对决已开始，拒绝失败。"
        return "拒绝成功，对决已结束。"


@plugin.handle({"超时结算"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    if (session := place.get(event.group_id)) and session.timeout() < 0:
        session.win = session.p2_uid if session.next == session.p1_uid else session.p1_uid
        return session.end()


@plugin.handle({"认输"}, {"user_id", "group_id", "nickname"})
async def _(event: Event):
    user_id = event.user_id
    session = place.get(event.group_id)
    if not session or session.p2_uid is None:
        return
    if user_id == session.p1_uid:
        session.win = session.p2_uid
    elif user_id == session.p2_uid:
        session.win = session.p1_uid
    else:
        return
    return session.end()


@plugin.handle({"游戏重置"}, {"user_id", "group_id", "nickname", "permission"})
async def _(event: Event):
    group_id = event.group_id
    session = place.get(group_id)
    if not session:
        return
    if session.timeout() > 0 and event.permission < 1:
        return f"当前游戏未超时。"
    del place[group_id]
    return "游戏已重置。"


russian_roulette = Game("俄罗斯轮盘", "开枪")


@plugin.handle({"俄罗斯轮盘", "装弹"}, {"user_id", "group_id", "nickname", "at"})
@russian_roulette.create(place)
async def _(session: Session, arg: str):
    bullet_num = to_int(arg)
    if bullet_num:
        bullet_num = random.randint(1, 6) if bullet_num < 1 or bullet_num > 6 else bullet_num
    else:
        bullet_num = 1
    bullet = [0, 0, 0, 0, 0, 0, 0]
    for i in random.sample([0, 1, 2, 3, 4, 5, 6], bullet_num):
        bullet[i] = 1
    session.data["bullet_num"] = bullet_num
    session.data["bullet"] = bullet
    session.data["index"] = 0
    if session.bet:
        prop, n = session.bet
        tip = f"\n本场下注：{prop.name} {n}"
    else:
        tip = ""
    tip += f"\n第一枪的概率为：{round(bullet_num * 100 / 7,2)}%"
    session.tip = str(bullet)
    return f"{' '.join('咔' for _ in range(bullet_num))}，装填完毕{tip}\n{session.create_info()}"


@plugin.handle({"开枪"}, {"user_id", "group_id", "nickname"})
@russian_roulette.action(place)
async def _(event: Event, session: Session):
    bullet = session.data["bullet"]
    index = session.data["index"]
    user_id = event.user_id
    MAG = bullet[index:]
    count = event.args_to_int() or 1
    l_MAG = len(MAG)
    if count < 0 or count > l_MAG:
        count = l_MAG
    shot_tip = f"连开{count}枪！\n" if count > 1 else ""
    if any(MAG[:count]):
        session.win = session.p2_uid if session.p2_uid == user_id else session.p1_uid
        random_tip = random.choice(["嘭！，你直接去世了", "眼前一黑，你直接穿越到了异世界...(死亡)", "终究还是你先走一步..."])
        result = f"{shot_tip}{random_tip}\n第 {index + MAG.index(1) + 1} 发子弹送走了你..."
        return session.end(result)
    else:
        session.nextround()
        session.data["index"] += count
        next_name = session.p1_nickname if session.next == session.p1_uid else session.p2_nickname
        random_tip = random.choice(
            [
                "呼呼，没有爆裂的声响，你活了下来",
                "虽然黑洞洞的枪口很恐怖，但好在没有子弹射出来，你活下来了",
                "看来运气不错，你活了下来",
            ]
        )
        return f"{shot_tip}{random_tip}\n下一枪中弹的概率：{round(session.data['bullet_num'] * 100 / (l_MAG - count),2)}%\n接下来轮到{next_name}了..."


dice = Game("掷骰子", "开数")


@plugin.handle({"摇色子", "摇骰子", "掷色子", "掷骰子"}, {"user_id", "group_id", "nickname", "at"})
@dice.create(place)
async def _(session: Session, arg: str):
    def dice_pt(dice_array: list):
        pt = 0
        for i in range(1, 7):
            if dice_array.count(i) <= 1:
                pt += i * dice_array.count(i)
            elif dice_array.count(i) == 2:
                pt += (100 + i) * (10 ** dice_array.count(i))
            else:
                pt += i * (10 ** (2 + dice_array.count(i)))
        return pt

    dice_array1 = [random.randint(1, 6) for _ in range(5)]
    session.data["dice_array1"] = dice_array1
    session.data["pt1"] = dice_pt(dice_array1)

    dice_array2 = [random.randint(1, 6) for _ in range(5)]
    session.data["dice_array2"] = dice_array2
    session.data["pt2"] = dice_pt(dice_array2)

    if session.bet:
        prop, n = session.bet
        n1 = prop.N(*manager.locate_account(session.p1_uid, session.group_id))
        n2 = prop.N(*manager.locate_account(session.p2_uid, session.group_id))
        session.data["bet_limit"] = min(n1, n2)
        tip = f"\n本场下注：{prop.name} {n}/次"
    else:
        tip = ""
    return f"哗啦哗啦~，骰子准备完毕{tip}\n{session.create_info()}"


@plugin.handle({"开数"}, {"user_id", "group_id", "nickname"})
@dice.action(place)
async def _(event: Event, session: Session):
    user_id = event.user_id
    if user_id == session.p1_uid:
        nickname = session.p1_nickname
        dice_array = session.data["dice_array1"]
        pt = session.data["pt1"]
    else:
        nickname = session.p2_nickname
        dice_array = session.data["dice_array2"]
        pt = session.data["pt2"]

    def pt_analyse(pt: int):
        array_type = []
        if (n := int(pt / 10000000)) > 0:
            pt -= n * 10000000
            array_type.append(f"满{n}")
        if (n := int(pt / 1000000)) > 0:
            pt -= n * 1000000
            array_type.append(f"串{n}")
        if (n := int(pt / 100000)) > 0:
            pt -= n * 100000
            array_type.append(f"条{n}")
        if (n := int(pt / 10000)) > 0:
            if n == 1:
                pt -= 10000
                n = int(pt / 100)
                array_type.append(f"对{n}")
            else:
                pt -= 20000
                n = int(pt / 100)
                array_type.append(f"两对{n}")
            pt -= n * 100
        if pt > 0:
            array_type.append(f"散{pt}")
        return " ".join(array_type)

    result = f"玩家：{nickname}\n组合：{' '.join(str(x) for x in dice_array)}\n点数：{pt_analyse(pt)}"
    if session.round == 2:
        if session.bet:
            prop, n = session.bet
            n += n
            session.bet = (prop, min([n, session.data["bet_limit"]]))
        pt1 = session.data["pt1"]
        pt2 = session.data["pt2"]
        session.win = session.p1_uid if pt1 > pt2 else session.p2_uid
        return session.end(result)
    session.nextround()
    return result + f"\n下一回合{session.p2_nickname}"


poker = Game("扑克对战", "出牌")


class PokerGame:
    suit = {0: "结束", 1: "防御", 2: "恢复", 3: "技能", 4: "攻击"}
    point = {0: "0", 1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8", 9: "9", 10: "10", 11: "J", 12: "Q", 13: "K"}

    def __init__(self) -> None:
        deck = random_poker(2)
        hand = deck[:3]
        deck = deck[3:]
        self.deck = deck + [(0, 0), (0, 0), (0, 0), (0, 0)]
        self.P1 = self.Gamer(hand, 20)
        self.P2 = self.Gamer([], 25, SP=2)

    @classmethod
    def card(cls, suit: int, point: int):
        return f"{cls.suit[suit]}{cls.point[point]}"

    class Gamer:
        def __init__(self, hand: list[tuple[int, int]], HP: int, ATK: int = 0, DEF: int = 0, SP: int = 0) -> None:
            self.hand = hand
            self.HP = HP
            self.ATK = ATK
            self.DEF = DEF
            self.SP = SP

        def status(self) -> str:
            return f"HP {self.HP} SP {self.SP} DEF {self.DEF}"

        def handcard(self) -> str:
            return "|".join(PokerGame.card(*card) for card in self.hand)


@plugin.handle({"扑克对战"}, {"user_id", "group_id", "nickname", "at"})
@poker.create(place)
async def _(session: Session, arg: str):
    poker_data = PokerGame()
    session.data["ACT"] = False
    session.data["poker"] = poker_data
    if session.bet:
        prop, n = session.bet
        tip = f"\n本场下注：{prop.name} {n}"
    else:
        tip = ""
    return f"唰唰~，随机牌堆已生成{tip}\n{session.create_info()}\nP1初始手牌\n{poker_data.P1.handcard()}"


@plugin.handle({"出牌"}, {"user_id", "group_id", "nickname"})
@poker.action(place)
async def _(event: Event, session: Session):
    if session.data["ACT"]:
        return
    user_id = event.user_id
    if not 1 <= (index := event.args_to_int()) <= 3:
        return "请发送【出牌 1/2/3】打出你的手牌。"
    index -= 1
    session.data["ACT"] = True
    session.nextround()
    poker_data: PokerGame = session.data["poker"]
    deck = poker_data.deck
    if user_id == session.p1_uid:
        active = poker_data.P1
        passive = poker_data.P2
        passive_name = session.p2_nickname
    else:
        active = poker_data.P2
        passive = poker_data.P1
        passive_name = session.p1_nickname
    msg = []

    # 出牌判定
    def action_ACE(active: PokerGame.Gamer, roll: int = 1):
        msg = [f"技能牌：{active.handcard()}"]
        for suit, point in active.hand:
            point = roll if point == 1 else point
            match suit:
                case 1:
                    active.DEF += point
                    msg.append(f"♤防御力强化了 {point}")
                case 2:
                    active.HP += point
                    msg.append(f"♡生命值增加了 {point}")
                case 3:
                    active.SP += point * 2
                    msg.append(f"♧技能点增加了 {point}")
                case 4:
                    active.ATK += point
                    msg.append(f"♢发动了攻击 {point}")
            active.SP -= point
            active.SP = 0 if active.SP < 0 else active.SP
        return msg

    suit, point = active.hand[index]
    if point == 1:
        roll = random.randint(1, 6)
        msg.append(f"发动ACE技能！六面骰子判定为 {roll}")
        msg += action_ACE(active, roll)
    else:
        match suit:
            case 1:
                active.ATK += point
                msg.append(f"♤发动了攻击{point}")
            case 2:
                active.HP += point
                msg.append(f"♡生命值增加了{point}")
            case 3:
                active.SP += point
                msg.append(f"♧技能点增加了{point}")
                roll = random.randint(1, 20)
                msg.append(f"二十面骰判定为{roll}点，当前技能点{active.SP}")
                if active.SP < roll:
                    msg.append("技能发动失败...")
                else:
                    msg.append("技能发动成功！")
                    del active.hand[index]
                    msg += action_ACE(active)
            case 4:
                active.ATK += point
                msg.append(f"♢发动了攻击{point}")
    # 敌方技能判定
    if passive.SP > 1:
        roll = random.randint(1, 20)
        msg.append(f"{passive_name} 二十面骰判定为{roll}点，当前技能点{passive.SP}")
        if passive.SP < roll:
            msg.append("技能发动失败...")
        else:
            msg.append("技能发动成功！")
            suit, point = deck[0]
            deck = deck[1:]
            msg.append(f"技能牌：{PokerGame.card(suit, point)}")
            match suit:
                case 1:
                    passive.DEF += point
                    msg.append(f"♤发动了防御 {point}")
                case 2:
                    passive.HP += point
                    msg.append(f"♡生命值增加了 {point}")
                case 3:
                    passive.SP += point * 2
                    msg.append(f"♧技能点增加了 {point}")
                case 4:
                    passive.ATK += point
                    msg.append(f"♢发动了反击 {point}")
            passive.SP -= point
            passive.SP = 0 if passive.SP < 0 else passive.SP
    # 回合结算
    if passive.ATK > active.DEF:
        active.HP += active.DEF - passive.ATK
    if active.ATK > passive.DEF:
        passive.HP += passive.DEF - active.ATK
    active.ATK = 0
    passive.ATK = 0
    passive.DEF = 0
    # 下回合准备
    hand = deck[0:3]
    passive.hand = hand
    deck = deck[3:]

    output = BytesIO()
    text_to_image(
        (
            f"玩家：{session.p1_nickname}\n状态：{poker_data.P1.status()}\n"
            "----\n"
            f"玩家：{session.p2_nickname}\n状态：{poker_data.P2.status()}\n"
            "----\n"
            f"当前回合：{passive_name}\n手牌：{passive.handcard()}"
        ),
        bg_color="white",
    ).save(output, format="png")
    msg = "\n".join(msg)

    async def result():
        yield msg
        await asyncio.sleep(0.03 * len(msg))
        yield output

    if active.HP < 1 or passive.HP < 1 or passive.HP > 40 or (0, 0) in hand:
        session.win = session.p1_uid if poker_data.P1.HP > poker_data.P2.HP else session.p2_uid
        return session.end(result)
    session.data["ACT"] = False
    return result


cantrell = Game("梭哈", "看牌|开牌")


@plugin.handle({"同花顺", "港式五张", "梭哈"}, {"user_id", "group_id", "nickname", "at"})
@cantrell.create(place)
async def _(session: Session, arg: str):
    level = to_int(arg)
    if level:
        level = 1 if level < 1 else level
        level = 5 if level > 5 else level
    else:
        level = 1
    deck = random_poker(range_point=(2, 15))

    def is_straight(points: list[int]):
        """
        判断是否为顺子
        """
        points = sorted(points)
        for i in range(1, len(points)):
            if points[i] - points[i - 1] != 1:
                return False
        return True

    def cantrell_pt(hand: list[tuple[int, int]]) -> tuple[int, str]:
        """
        牌型点数
        """
        pt = 0
        name = []
        suits, points = zip(*hand)
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

    def max_hand(hands: list[list[tuple[int, int]]]):
        max_hand = hands[0]
        max_pt, max_name = cantrell_pt(max_hand)
        for hand in hands[1:]:
            pt, name = cantrell_pt(hand)
            if pt > max_pt:
                max_pt = pt
                max_name = name
                max_hand = hand
        return max_hand, max_pt, max_name

    if level == 1:
        hand1 = deck[0:5]
        pt1, name1 = cantrell_pt(hand1)
        hand2 = deck[5:10]
        pt2, name2 = cantrell_pt(hand2)
    else:
        deck = [deck[i : i + 5] for i in range(0, 50, 5)]
        hand1, pt1, name1 = max_hand(deck[0:level])
        hand2, pt2, name2 = max_hand(deck[level : 2 * level])

    session.data["hand1"] = hand1
    session.data["hand2"] = hand2
    session.data["pt1"] = pt1
    session.data["pt2"] = pt2
    session.data["name1"] = name1
    session.data["name2"] = name2
    if session.bet:
        prop, n = session.bet
        session.data["bet_limit"]
        tip = f"\n本场下注：{prop.name} {n}"
    else:
        tip = ""
    return f"唰唰~，随机牌堆已生成，等级：{level}{tip}\n{session.create_info()}"


@plugin.handle({"看牌"}, {"user_id", "group_id", "nickname"})
@cantrell.action(place)
async def _(event: Event, session: Session):
    if not event.is_private():
        return "请私信回复 看牌 查看手牌"
    expose = session.round + 1 // 2 + 2
    session.delay()
    if event.user_id == session.p1_uid:
        hand = session.data["hand1"]
    else:
        hand = session.data["hand2"]
    cards = "\n".join(f"【{poker_suit[suit]},{poker_point[point]}】" for suit, point in hand[0:expose])
    return f"你的手牌：\n{cards}"


@plugin.handle({"看牌"}, {"user_id", "group_id", "nickname"})
@cantrell.action(place)
async def _(event: Event, session: Session):
    if not event.is_private():
        return "请私信回复 看牌 查看手牌"
    expose = session.round + 1 // 2 + 2
    session.delay()
    if event.user_id == session.p1_uid:
        hand = session.data["hand1"]
    else:
        hand = session.data["hand2"]
    cards = "\n".join(f"【{poker_suit[suit]},{poker_point[point]}】" for suit, point in hand[0:expose])
    return f"你的手牌：\n{cards}"


@plugin.handle({"开牌"}, {"user_id", "group_id", "nickname"})
@cantrell.action(place)
async def _(event: Event, session: Session):
    if session.bet:
        prop, n = session.bet
        n += session.data["bet"]
        session.bet = (prop, min([n, n1, n2]))

    def cantrell_play(self, user_id: int, gold: int):
        """
        开牌
        """
        session = self.session
        gold = self.gold if gold == None else gold
        gold = min(gold, session.bet_limit - session.gold)
        if gold > self.max_bet_gold:
            return f"开牌金额不能超过{self.max_bet_gold}"
        expose = session.round / 2
        session.nextround()
        session.time += 120
        if expose == int(expose):
            gold = max(gold, self.gold)
            session.gold += gold
            expose = int(expose) + 2
            hand1 = self.hand1[0:expose]
            hand2 = self.hand2[0:expose]
            cantrell_suit = self.cantrell_suit
            cantrell_point = self.cantrell_point

            if expose == 5:
                session.win = session.p1_uid if self.pt1[0] > self.pt2[0] else session.p2_uid
                msg = (
                    "P1手牌：\n"
                    "|"
                    + "".join(f"{cantrell_suit[suit]}{cantrell_point[point]}|" for suit, point in self.hand1)
                    + f"\n牌型：\n{self.pt1[1]}"
                    "\n----\n"
                    "P2手牌：\n"
                    "|"
                    + "".join(f"{cantrell_suit[suit]}{cantrell_point[point]}|" for suit, point in self.hand2)
                    + f"\n牌型：\n{self.pt2[1]}"
                )
                self.end(linecard_to_png(msg, width=880))
            else:
                msg = (
                    f"玩家：{session.p1_nickname}\n"
                    "手牌：\n"
                    f'|{"".join(f"{cantrell_suit[suit]}{cantrell_point[point]}|" for suit, point in hand1)}{(5 - expose)*"   |"}'
                    "\n----\n"
                    f"玩家：{session.p2_nickname}\n"
                    "手牌：\n"
                    f'|{"".join(f"{cantrell_suit[suit]}{cantrell_point[point]}|" for suit, point in hand2)}{(5 - expose)*"   |"}'
                )
                return linecard_to_png(f"您已跟注{gold}金币\n" if gold else "" + msg, width=880)
        else:
            self.gold = gold
            return f"您已加注{gold}金币，" if gold else "" + f"请{session.p2_nickname}看牌|开牌"
