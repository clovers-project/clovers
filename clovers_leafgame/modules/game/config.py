from pydantic import BaseModel


class Config(BaseModel):
    # 超时时间
    timeout: int = 60
    # 默认赌注
    default_bet: int = 200
    # 默认显示字体
    fontname = "simsun"

    """+++++++++++++++++
    ——————————
       下面是赛马设置
    ——————————
    +++++++++++++++++"""

    # 跑道长度
    setting_track_length = 20
    # 随机位置事件，最小能到的跑道距离
    setting_random_min_length = 0
    # 随机位置事件，最大能到的跑道距离
    setting_random_max_length = 15
    # 每回合基础移动力最小值
    base_move_min = 1
    # 每回合基础移动力最大值
    base_move_max = 3
    # 最大支持玩家数
    max_player = 8
    # 最少玩家数
    min_player = 2
    # 事件概率 = event_rate / 1000
    event_rate = 450
