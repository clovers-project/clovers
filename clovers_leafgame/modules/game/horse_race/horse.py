import random
from pydantic import BaseModel


class Event(BaseModel):
    event_name: str = "未知事件"
    """事件名称"""
    only_key: int | None = None
    """唯一事件码，不为None则一场只触发一次"""
    describe: str
    """事件描述"""
    target: int
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
    live: int
    """复活事件：为1则目标复活"""
    move: int
    """位移事件：目标立即进行相当于参数值的位移"""
    track_to_location: int | None = None
    """随机位置事件：有值则让目标移动到指定位置"""
    track_random_location: int
    """随机位置事件：为1则让目标随机位置（位置范围为可设定值，见setting.py）"""
    buff_time_add: int = 0
    """buff持续时间调整事件：目标所有buff增加/减少回合数"""
    del_buff: str | None = None
    """删除buff事件：下回合删除目标含特定buff_tag的所有buff"""
    track_exchange_location: int = 0
    """换位事件：值为1则与目标更换位置 （仅target为1,6时生效）"""
    random_event_once: list["Event"] = []
    """一次性随机事件"""


class Buff(BaseModel):
    name: str
    round_start: int
    round_end: int
    move_min: int
    move_max: int
    buffs: object
    event_in_buff: list[object]


class Horse:
    def __init__(self, horsename, uid, id, location=0, round=0):
        self.horse: str = horsename
        self.playeruid: str = uid
        self.player = id
        self.buff: list[Buff] = []
        self.delay_events = []
        self.horse_fullname = horsename
        self.round = round
        self.location = location
        self.location_add = 0
        self.location_add_move = 0

    # =====马儿buff增加
    def add_buff(self, buff_name: str, round_start: int, round_end: int, move_min: int, move_max: int, buffs, event_in_buff=[]):
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

    # =====马儿指定buff移除：
    def del_buff(self, del_buff_key):
        self.buff = [buff for buff in self.buff if buff.name != del_buff_key]

    # =====马儿查找有无buff（查参数非名称）：(跳过计算回合数，只查有没有）
    def find_buff(self, find_buff_key):
        return any(True for buff in self.buff if buff.name == find_buff_key)

    # =====马儿超时buff移除：
    def del_buff_overtime(self, round):
        for i in range(len(self.buff) - 1, -1, -1):
            if self.buff[i][2] < round:
                del self.buff[i]

    # =====马儿buff时间延长/减少：
    def buff_addtime(self, round_add):
        for i in range(0, len(self.buff)):
            self.buff[i][2] += round_add

    # =====马儿是否止步：
    def is_stop(self) -> bool:
        for i in range(0, len(self.buff)):
            try:
                self.buff[i].index("locate_lock", 6)
                if self.buff[i][1] <= self.round:
                    return True
            except ValueError:
                pass
        return False

    # =====马儿是否已经离开：
    def is_away(self) -> bool:
        for i in range(0, len(self.buff)):
            try:
                self.buff[i].index("away", 5)
                if self.buff[i][1] <= self.round:
                    return True
            except ValueError:
                pass
        return False

    # =====马儿是否已经死亡：
    def is_die(self) -> bool:
        for i in range(0, len(self.buff)):
            try:
                self.buff[i].index("die", 5)
                if self.buff[i][1] <= self.round:
                    return True
            except ValueError:
                pass
        return False

    # =====马儿全名带buff显示：
    def fullname(self):
        fullname = f""
        for i in range(0, len(self.buff)):
            if self.buff[i][1] <= self.round:
                fullname += "<" + self.buff[i][0] + ">"
        self.horse_fullname = fullname + self.horse

    # =====马儿移动计算（事件提供的本回合移动）：
    def location_move_event(self, move):
        self.location_add_move += move

    # =====马儿移动至特定位置计算（事件提供移动）：
    def location_move_to_event(self, move_to):
        self.location_add_move += move_to - self.location

    # =====马儿移动计算：
    def location_move(self):
        if self.location != setting_track_length:
            self.location_add = self.move() + self.location_add_move
            self.location += self.location_add
            if self.location > setting_track_length:
                self.location_add -= self.location - setting_track_length
                self.location = setting_track_length
            if self.location < 0:
                self.location_add -= self.location
                self.location = 0

    # =====马儿移动量计算：
    def move(self):
        if self.is_stop() == True:
            return 0
        if self.is_die() == True:
            return 0
        if self.is_away() == True:
            return 0
        move_min = 0
        move_max = 0
        for i in range(0, len(self.buff)):
            if self.buff[i][1] <= self.round:
                move_min += self.buff[i][3]
                move_max += self.buff[i][4]
        return random.randint(move_min + base_move_min, move_max + base_move_max)

    # =====赛马玩家战况显示：
    def display(self):
        display = f""
        if self.find_buff("hiding") == False:
            if self.location_add < 0:
                display += "[" + str(self.location_add) + "]"
            else:
                display += "[+" + str(self.location_add) + "]"
            for i in range(0, setting_track_length - self.location):
                display += "."
            display += self.horse_fullname
            for i in range(setting_track_length - self.location, setting_track_length):
                display += "."
        else:
            display += "[+？]"
            for i in range(0, setting_track_length):
                display += "."
        return display
