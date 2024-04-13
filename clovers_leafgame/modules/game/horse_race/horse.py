import random
from pydantic import BaseModel

Event_list = list[tuple[int, "Event"]]
"""
[[概率值1, {事件}], [概率值2, {事件}], ......]

[[延迟回合数1, {事件}], [延迟回合数2, {事件}], ......]
"""


class Event(BaseModel):
    event_name: str = "未知事件"
    """事件名称"""
    only_key: int | None = None
    """唯一事件码，不为None则一场只触发一次"""
    describe: str = ""
    """事件描述"""
    target: int = -1
    """
    事件生效目标
        0: 自己
        1: 随机选择一个非自己的目标
        2: 全部
        3: 除自身外全部
        4: 全场随机一个目标
        5: 自己和一位其他目标
        6: 随机一侧赛道的马儿
        7: 自己两侧赛道的马儿
    """
    target_is_buff: str | None = None
    """筛选事件生效目标有buff名"""
    target_no_buff: str | None = None
    """筛选事件生效目标无buff名"""
    live: int = 0
    """复活事件：为1则目标复活"""
    move: int = 0
    """位移事件：目标立即进行相当于参数值的位移"""
    track_to_location: int | None = None
    """随机位置事件：有值则让目标移动到指定位置"""
    track_random_location: int | None = None
    """随机位置事件：为1则让目标随机位置（位置范围为可设定值，见setting.py）"""
    buff_time_add: int = 0
    """buff持续时间调整事件：目标所有buff增加/减少回合数"""
    del_buff: str | None = None
    """删除buff事件：下回合删除目标含特定buff_tag的所有buff"""
    track_exchange_location: int = 0
    """换位事件：值为1则与目标更换位置 （仅target为1,6时生效）"""
    random_event_once: Event_list = []
    """一次性随机事件"""
    die: int = 0
    """死亡：为1则目标死亡，此参数生成的buff默认持续到9999回合"""
    die_name: str = "死亡"
    """die的自定义名称"""
    away: int = 0
    """离开：为1则目标死亡，此参数生成的buff默认持续到9999回合"""
    away_name: str = "离开"
    """away的自定义名称"""
    rounds: int = 0
    """buff持续回合数"""
    name: str = "未命名buff"
    """buff名称，turn值>0时为必要值"""
    move_max: int = 0
    """该buff提供马儿每回合位移值区间的最大值"""
    move_min: int = 0
    """该buff提供马儿每回合位移值区间的最小值"""
    buffs: set = set()
    """buff组合，详见Buff类buffs字段文档"""
    random_event: Event_list = []
    """持续性随机事件，以buff形式存在"""
    delay_event: tuple[int, "Event"] | None = None
    """延迟事件（以当前事件的targets为发起人的事件）：前者为多少回合后，需>1"""
    delay_event_self: tuple[int, "Event"] | None = None
    """延迟事件（以当前事件发起人为发起人的事件）：前者为多少回合后，需>1"""
    another_event: "Event | None" = None
    """同步事件（以当前事件的targets为发起人的事件），执行此事件后立马执行该事件"""
    another_event_self: "Event | None" = None
    """同步事件（以当前事件发起人为发起人的事件），执行此事件后立马执行该事件"""
    add_horse: dict = {}
    """增加一匹马事件"""
    replace_horse: dict = {}
    """替换一匹马事件"""


class Buff(BaseModel):
    name: str
    """buff名称，turn值>0时为必要值"""
    round_start: int
    """buff开始回合数"""
    round_end: int
    """buff结束回合数"""
    move_min: int
    move_max: int
    buffs: set[str]
    """
    locate_lock: 止步，目标无法移动
    vertigo: 眩晕，目标无法移动，且不主动执行事件（暂定）
    hiding: 隐身：不显示目标移动距离及位置
    others: 自定义buff_tag，仅标识用buff_tag填写处，也可以填入常规buff_tag并正常生效
    """
    event_in_buff: Event_list


class Horse:
    def __init__(self, horsename, uid, id, location=0, round=0):
        self.horse: str = horsename
        self.playeruid: str = uid
        self.player = id
        self.buff: list[Buff] = []
        self.delay_events: Event_list = []
        self.horse_fullname = horsename
        self.round = round
        self.location = location
        self.location_add = 0
        self.location_add_move = 0

    def add_buff(
        self,
        buff_name: str,
        buffs: set[str],
        round_start: int,
        round_end: int,
        move_min: int = 0,
        move_max: int = 0,
        event_in_buff=[],
    ):
        """马儿buff增加"""
        if move_min > move_max:
            move_max = move_min
        buff = Buff(
            name=buff_name,
            round_start=round_start,
            round_end=round_end,
            move_min=move_min,
            move_max=move_max,
            buffs=buffs,
            event_in_buff=event_in_buff,
        )
        self.buff.append(buff)

    def del_buff(self, del_buff_key):
        """马儿指定buff移除"""
        self.buff = [buff for buff in self.buff if del_buff_key not in buff.buffs]

    def find_buff(self, find_buff_key):
        """马儿查找有无buff（查参数非名称）：(跳过计算回合数，只查有没有）"""
        return any(True for buff in self.buff if find_buff_key in buff.buffs)

    def buff_addtime(self, round_add):
        """马儿buff时间延长/减少"""
        for buff in self.buff:
            buff.round_end += round_add

    def is_stop(self) -> bool:
        """马儿是否止步"""
        return self.find_buff("locate_lock")

    def is_away(self) -> bool:
        """马儿是否已经离开"""
        return self.find_buff("away")

    def is_die(self) -> bool:
        """马儿是否已经死亡"""
        return self.find_buff("die")

    # =====马儿全名带buff显示：
    def fullname(self):
        self.horse_fullname = "".join(f"<{buff.name}>" for buff in self.buff) + self.horse

    def location_move(self, move):
        """马儿移动计算（事件提供的本回合移动）"""
        self.location_add_move += move

    def location_to(self, move_to):
        """马儿移动至特定位置计算（事件提供移动）"""
        self.location_add_move = move_to - self.location

    def move(self, move_min: int, move_max: int, track_length: int):
        """马儿移动计算"""
        if self.is_stop() or self.is_die() or self.is_away():
            base_move = 0
        else:
            for buff in self.buff:
                move_min += buff.move_min
                move_max += buff.move_max
            base_move = random.randint(move_min, move_max)
        self.location_add = base_move + self.location_add_move
        self.location += self.location_add
        self.location = max(0, self.location)
        self.location = min(track_length, self.location)

    # =====赛马玩家战况显示：
    def display(self, track_length: int):
        if self.find_buff("hiding"):
            return "[+?]" + "." * track_length

        start = f"[{self.location_add}]" if self.location_add < 0 else f"[+{self.location_add}]"
        track = ["." for _ in range(track_length - 1)]
        track.insert(self.location, self.horse_fullname)
        return start + "".join(track)
