from pydantic import BaseModel


class Config(BaseModel):
    # 每日签到的范围
    sign_gold: tuple[int, int] = (200, 500)
    # 标记字符串
    clovers_marking = "ＬＵＣＫＹ ＣＬＯＶＥＲ"
    revolution_marking = " ＣＡＰＩＴＡＬＩＳＴ "
    debug_marking = "  ＯＦＦＩＣＩＡＬ  "
