import random
from clovers_leafgame.main import plugin, manager
from clovers_leafgame.core.clovers import Event
from .core import Session, Game, to_int
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
    return f"{session.p2_nickname}接受了对决！\n本场对决为【{session.game.name}】\n{tip}请{session.p1_nickname}发送指令\n{session.game.action_commands_tips}"


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


russian_roulette = Game("俄罗斯轮盘", {"俄罗斯轮盘", "装弹"}, {"开枪"})


@plugin.handle(russian_roulette.create_commands, {"user_id", "group_id", "nickname", "at"})
@russian_roulette.create(place)
async def _(session: Session, arg: str):
    bullet_num = to_int(arg)
    if bullet_num:
        bullet_num = random.randint(1, 6) if bullet_num < 1 or bullet_num > 6 else bullet_num
    else:
        bullet_num = 1
    bullet = [0, 0, 0, 0, 0, 0]
    for i in random.sample([0, 1, 2, 3, 4, 5, 6], bullet_num):
        bullet[i] = 1
    session.data["bullet_num"] = bullet_num
    session.data["bullet"] = bullet
    session.data["index"] = 0
    if session.bet:
        prop, n = session.bet
        tip = f"\n本场金额：{prop.name} {n}"
    else:
        tip = ""
    tip += f"\n第一枪的概率为：{round(bullet_num * 100 / 7,2)}%"
    return f"{' '.join('咔' for _ in range(bullet_num))}，装填完毕{tip}\n{session.create_info()}"


@plugin.handle(russian_roulette.action_commands, {"user_id", "group_id", "nickname"})
@russian_roulette.action(place)
async def _(event: Event, session: Session):
    bullet = session.data["bullet"]
    index = session.data["index"]
    user_id = event.user_id
    MAG = bullet[index:]
    count = event.args_to_int()
    l_MAG = len(MAG)
    if count < 1 or count > l_MAG:
        count = l_MAG
    shot_tip = f"连开{count}枪！\n" if count > 1 else ""
    if any(MAG[:count]):
        session.win = session.p2_uid if session.p2_uid == user_id else session.p1_uid
        random_tip = random.choice(["嘭！，你直接去世了", "眼前一黑，你直接穿越到了异世界...(死亡)", "终究还是你先走一步..."])
        result = f"{shot_tip}{random_tip}\n第 {index + MAG.index(1) + 1} 发子弹送走了你..."
        session.end(result)
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
        return f"{shot_tip}{random_tip}\n下一枪中弹的概率：{round(session.data["bullet_num"] * 100 / (l_MAG - count),2)}%\n接下来轮到{next_name}了..."
