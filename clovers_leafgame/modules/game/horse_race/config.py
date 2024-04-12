from pydantic import BaseModel


class Config(BaseModel):
    # 玩家人数范围
    range_of_player_numbers = (2, 8)
    # 跑道长度
    setting_track_length = 20
    # 随机位置事件，能够随机到的跑道范围
    random_move_range: tuple[float, float] = (0, 0.8)
    # 每回合基础移动力最小值
    base_move_min = 1
    # 每回合基础移动力最大值
    base_move_max = 3
    # 事件概率 = event_rate / 1000
    event_randvalue = 450
