from pydantic import BaseModel
from pathlib import Path


class Config(BaseModel):
    # 超时时间
    timeout: int = 120
    # 主路径
    main_path: str = str(Path("LiteGames").absolute())
    # 每日签到的范围
    sign_gold: tuple[int, int] = (200, 500)
    # 每日补贴的范围
    security_gold: tuple[int, int] = (100, 300)
    # 重置签到的范围
    revolt_gold: tuple[int, int] = (1000, 2000)
    # 重置冷却时间，设置为0禁用发起重置
    revolt_cd: int = 28800
    # 重置的基尼系数
    revolt_gini: float = 0.68
    # 最大赌注
    max_bet_gold: int = 2000
    # 最大赌注
    company_public_gold: int = 20000
    # 默认赌注
    bet_gold: int = 200
    # 标记字符串
    clovers_marking = "ＬＵＣＫＹ ＣＬＯＶＥＲ"
    revolution_marking = " ＣＡＰＩＴＡＬＩＳＴ "
    debug_marking = "  ＯＦＦＩＣＩＡＬ  "
    # 默认显示字体
    fontname = "simsun"
    # 默认备用字体
    fallback_fonts = [
        "Arial",
        "Tahoma",
        "Microsoft YaHei",
        "Segoe UI",
        "Segoe UI Emoji",
        "Segoe UI Symbol",
        "Helvetica Neue",
        "PingFang SC",
        "Hiragino Sans GB",
        "Source Han Sans SC",
        "Noto Sans SC",
        "Noto Sans CJK JP",
        "WenQuanYi Micro Hei",
        "Apple Color Emoji",
        "Noto Color Emoji",
    ]

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
