import random
import math
from collections.abc import Callable
from .horse import Horse, Event
from clovers_core.config import config as clovers_config
from .config import Config

config = Config.parse_obj(clovers_config.get(__package__, {}))

min_player_numbers, max_player_numbers = config.range_of_player_numbers
track_length = config.setting_track_length
random_move_min,random_move_max = config.random_move_range
random_move_range = int(random_move_min*track_length),int(random_move_max*track_length)


class RaceWorld:
    def __init__(self):
        self.racetrack: list[Horse] = []
        """赛马场跑道"""
        self.track_length = track_length
        """跑道长度"""
        self.min_player_numbers: int = min_player_numbers
        """最少玩家数"""
        self.max_player_numbers: int = max_player_numbers
        """最多玩家数"""
        self.status: int = 0
        """状态指示器：0为马儿进场未开始，1为开始，2为暂停（测试用）"""
        self.round: int = 0

        self.only_keys = set()
        """唯一事件记录"""
        self.events_list = []

    def join_horse(self, horse_name: str, user_id: str, user_name: str, location=0, round=0):
        """
        增加赛马位
        """
        if self.status != 0:
            return
        l = len(self.racetrack)
        if l >= self.max_player_numbers:
            return "> 加入失败！\n> 赛马场就那么大，满了满了！"
        if any(True for horse in self.racetrack if horse.playeruid == user_id):
            return "> 加入失败！\n> 您已经加入了赛马场!"
        self.racetrack.append(Horse(horse_name, user_id, user_name, location, round))
        horse_name = horse_name[:1] + "酱" if len(horse_name) >= 7 else horse_name
        return f"> {user_name} 加入赛马成功\n> 赌上马儿性命的一战即将开始!\n> 赛马场位置:{l + 1}/{self.max_player_numbers}"

    def event_main(self, horse: Horse, event: Event, event_delay_key=0):
        # 该马儿是否死亡/离开/眩晕，死亡则结束事件链
        if event_delay_key == 0 and (horse.is_die() or horse.is_away() or horse.find_buff("vertigo")):
            return
        # 读取事件限定值
        if only_key := event.only_key:
            if self.is_race_only_key_in(only_key):
                return
            else:
                self.only_keys.add(only_key)
        # 读取 target 目标，计算<0><1>， target_name_0 ， target_name_1
        targets = []
        target_name_0 = horse.horse_fullname
        match event.target:
            case 0:
                targets = [horse]
                target_name_1 = target_name_0
            case 1:
                target = random.choice([x for x in self.racetrack if not x is horse])
                targets = [target]
                target_name_1 = target.horse_fullname
            case 2:
                targets = self.racetrack
                target_name_1 = "所有马儿"
            case 3:
                targets = [x for x in self.racetrack if not x is horse]
                target_name_1 = "其他所有马儿"
            case 4:
                target = random.choice(self.racetrack)
                targets = [target]
                target_name_1 = target.horse_fullname
            case 5:
                target = random.choice([x for x in self.racetrack if not x is horse])
                targets = [target, horse]
                target_name_1 = target.horse_fullname
            case 6:
                index = self.racetrack.index(horse)
                side = [x for x in [index + 1, index - 1] if 0 <= x < len(self.racetrack)]
                target = self.racetrack[random.choice(side)]
                targets = [target]
                target_name_1 = target.horse_fullname
            case 7:
                index = self.racetrack.index(horse)
                side = [x for x in [index + 1, index - 1] if 0 <= x < len(self.racetrack)]
                targets = [self.racetrack[i] for i in side]
                target_name_1 = f"在{horse.horse_fullname}两侧的马儿"
            case _:
                return
        # 判定 target_is_buff
        if event.target_is_buff:
            targets = [x for x in targets if x.find_buff(event.target_is_buff)]
        # 判定 target_no_buff
        if event.target_is_buff:
            targets = [x for x in targets if not x.find_buff(event.target_is_buff)]
        # 无目标则结束事件
        if not targets:
            return
        # 读取 event_name
        event_name = event.event_name
        # 读取 describe 事件描述
        print(f"执行事件: {event_name}")
        print(f"<0>为：{target_name_0}，<1>为：{target_name_1}")
        # 读取 describe 事件描述
        describe = [event.describe.replace("<0>", target_name_0).replace("<1>", target_name_1)]

        def action(targets:list[Horse],callback:Callable[...,None],*args):
            for horse in targets:
                callback(horse,*args)

        """===============以下为一次性事件==============="""
        if event.live == 1:
            action(targets,lambda horse:horse.del_buff("die"))
        if event.move:
            action(targets,lambda horse,move:horse.location_move_event(move),event.move)
        if not event.track_to_location is None:
            action(targets,lambda horse,move_to:horse.location_move_to_event(move_to),event.track_to_location)
        if event.track_random_location == 1:
            action(targets,lambda horse:horse.location_move_to_event(random.randint(*random_move_range),event.track_to_location))
        if event.buff_time_add:
            action(targets,lambda horse,time_add:horse.buff_addtime(time_add),event.buff_time_add)
        if event.del_buff:
            action(targets,lambda horse,del_buff:horse.del_buff(del_buff),event.del_buff)
        if event.track_exchange_location == 1 and target in {1,6}:
            # 马儿互换位置
            target = targets[0]
            location =    target.location,horse.location   
            horse.location_move_to_event(location[0])
            target.location_move_to_event(location[1])
        if random_event_once:=event.random_event_once:
            def action_once_event(horse:Horse,event_list:list[Event],log_pad:list[str]):
                for event in event_list:
                    


            action(targets,lambda horse,event_once:horse.del_buff(del_buff),event.del_buff)


        # 一次性随机事件
        if event["random_event_once"] != []:
            random_event_once = event["random_event_once"]
            random_event_once_num = len(random_event_once)
            for i in targets:
                for j in range(0, random_event_once_num):
                    random_event_once_rate = random.randint(0, random_event_once[random_event_once_num - 1][0])
                    if random_event_once_rate <= random_event_once[j][0]:
                        event_once = random_event_once[j][1]
                        break
                describe += event_main(race, i, event_once, 1)
        # ===============以下为永久事件===============
        # buff_tag，死亡：为1则目标死亡，此参数生成的buff默认持续999回合
        # buff_tag：die的自定义名称，不填为“死亡”
        if event["die"] == 1:
            event_die(race, targets, event["die_name"])
        # buff_tag，离开：为1则目标离开，此参数生成的buff默认持续999回合
        # buff_tag：away的自定义名称，不填为“离开”
        if event["away"] == 1:
            event_away(race, targets, event["away_name"])
        # ==============================连锁事件预留位置，暂时没做

        # ===============以下为buff事件===============
        # "rounds": 0,                #buff持续回合数
        # "name": "xxx",              #buff名称，turn值>0时为必要值
        # "move_max": 0,              #该buff提供马儿每回合位移值区间的最大值（move_max若小于move_min，则move_max以move_min值为准）
        # "move_min": 0,              #该buff提供马儿每回合位移值区间的最小值
        # "locate_lock": 0,           #buff_tag，止步：若为1则目标无法移动
        # "vertigo": 0,               #buff_tag，眩晕：若为1则目标无法移动，且不主动执行事件（暂定）
        # "hiding": 0,                #buff_tag，隐身：不显示目标移动距离及位置
        # "other_buff": ["buff1", "buff2", ....]
        #                            #自定义buff_tag，仅标识用buff_tag填写处，也可以填入常规buff_tag并正常生效
        # "random_event": [[概率值1, {事件}], [概率值2, {事件}], ......],
        # 此为持续性随机事件，以buff形式存在，部分详见文末
        if event["rounds"] > 0:
            rounds = event["rounds"]
            buffs = []
            buff_name = event["name"]
            move_max = event["move_max"]
            move_min = event["move_min"]
            if event["locate_lock"] == 1:
                buffs.append("locate_lock")
            if event["vertigo"] == 1:
                buffs.append("locate_lock")
                buffs.append("vertigo")
            if event["hiding"] == 1:
                buffs.append("hiding")
            if event["other_buff"] != []:
                buffs.extend(event["other_buff"])
            event_in_buff = event["random_event"]
            event_add_buff(race, targets, buff_name, rounds, buffs, move_min, move_max, event_in_buff)
        # ===============以下为延迟事件===============
        # 延迟事件（以当前事件的targets为发起人的事件）：前者为多少回合后，需>1
        delay_event = event["delay_event"]
        if delay_event != []:
            event_delay_rounds = delay_event[0]
            if event_delay_rounds > 1:
                event_delay = delay_event[1]
                for i in targets:
                    race.player[i].delay_events.append([race.round + event_delay_rounds, event_delay])
        # 延迟事件（以当前事件发起人为发起人的事件）：前者为多少回合后，需>1
        delay_event_self = event["delay_event_self"]
        if delay_event_self != []:
            event_delay_rounds_self = delay_event_self[0]
            if event_delay_rounds_self > 1:
                event_delay_self = delay_event_self[1]
                race.player[horse_i].delay_events.append([race.round + event_delay_rounds_self, event_delay_self])

        # ===============以下同步事件===============
        # 同步事件（以当前事件的targets为发起人的事件），执行此事件后立马执行该事件
        another_event = event["another_event"]
        if another_event != {}:
            for i in targets:
                describe += event_main(race, i, another_event, 1)
        # 同步事件（以当前事件发起人为发起人的事件），执行此事件后立马执行该事件
        another_event_self = event["another_event_self"]
        if another_event_self != {}:
            describe += event_main(race, horse_i, another_event_self, 1)
        # ==========永久事件2，换赛道/加马==========
        # 增加一匹马事件
        if event["add_horse"] != {}:
            add_horse_event = event["add_horse"]
            add_horse_name = add_horse_event["horsename"]
            add_horse_id = add_horse_event["owner"]
            try:
                add_horse_uid = add_horse_event["uid"]
            except KeyError:
                add_horse_uid = 0
            try:
                add_horse_location = add_horse_event["location"]
            except KeyError:
                add_horse_location = 0
            logger.info(f"创建马{add_horse_name},{str(add_horse_uid)}, {add_horse_id}")
            race.add_player(add_horse_name, add_horse_uid, add_horse_id, add_horse_location, race.round)
        # 替换一匹马事件
        replace_event = event["replace_horse"]
        if replace_event != {}:
            if target == 0 or target == 1 or target == 4 or target == 6:
                try:
                    replace_name = replace_event["horsename"]
                except KeyError:
                    replace_name = race.player[targets[0]].horse
                try:
                    replace_id = replace_event["owner"]
                except KeyError:
                    replace_id = race.player[targets[0]].player
                try:
                    replace_uid = replace_event["uid"]
                except KeyError:
                    replace_uid = race.player[targets[0]].playeruid
                logger.info(f"替换事件{replace_name}, {str(replace_uid)}, {replace_id}")
                race.player[targets[0]].replace_horse_ex(replace_name, replace_uid, replace_id)
        return describe
            logger.info(f"事件名 {event_name} 执行故障")
            return f"事件名 {event_name} 执行故障"

    def nextround(self):
        """
        回合开始，回合数+1
        """
        self.round += 1
        event_log = []
        for horse in self.racetrack:
            horse.round = self.round
            horse.location_add_move = 0
            # 移除超时buff
            horse.del_buff_overtime(self.round)
            # 马儿全名计算
            horse.fullname()
            # 延时事件触发
            for delay_event in horse.delay_events:
                event_log.append(self.event_main(horse, delay_event, 1))
            # buff随机事件触发
            for buff in horse.buff:
                event_in_buff = buff.event_in_buff
                event_in_buff_num = len(event_in_buff)
                event_in_buff_rate = random.randint(0, event_in_buff[:-1][0])
                for inner_buff in event_in_buff:
                    if event_in_buff_rate < inner_buff[0]:
                        event_log.append(self.event_main(horse, inner_buff[1], 1))
                        break
            # 随机事件判定
            event_log.append(self.event_main(horse, random.choices(self.events_list), 1))
            # 马儿移动,包含死亡/离开/止步判定
            horse.location_move()
        return "\n".join(event_log)

    def is_die_all(self) -> bool:
        """
        所有马儿是否死亡/离开
        """
        return all(True for horse in self.racetrack if horse.is_die() or horse.is_away())

    def is_win_all(self):
        """
        所有马儿是否到终点
        """
        return [horse for horse in self.racetrack if horse.location >= self.track_length]

    def is_race_only_key_in(self, key):
        """
        事件唯一码查询
        """
        return key in self.race_only_keys

    def add_race_only_key(self, key):
        """
        事件唯一码增加
        """
        self.race_only_keys.append(key)
