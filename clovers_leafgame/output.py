from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG
from io import BytesIO

from .item.prop import Prop
from .core.data import Bank, Item, Stock
from .utils.linecard import FontManager, linecard, info_splicing
from .utils.tools import format_number
from .main import config, manager

main_path = config.main_path

font_manager = FontManager(
    config.fontname,
    config.fallback_fonts,
    (30, 40, 60),
)
# 加载或创建背景图片路径
BG_PATH = Path(main_path) / "BG_image"
BG_PATH.mkdir(exist_ok=True, parents=True)


def info_card(info, user_id, BG_type=None):
    extra = manager.locate_user(user_id).extra
    BG_type = BG_type or extra.get("BG_type", "#FFFFFF99")
    bg_path = BG_PATH / f"{user_id}.png"
    if not bg_path.exists():
        bg_path = BG_PATH / "default.png"
    try:
        return info_splicing(info, bg_path, spacing=10, BG_type=BG_type)
    except:
        if "BG_type" in extra:
            del extra["BG_type"]


def endline(tip: str) -> str:
    return f"----\n[right][color][grey][font][][30]{tip}"


def bank_to_data(bank: Bank, locate_item):
    return [(i, v) for k, v in bank.items() if v != 0 and (i := locate_item(k))]


def bank_card(data: list[tuple[Prop, int]]):
    data.sort(key=lambda x: x[0].rare)

    def result(prop: Prop, n: int):
        quant = {0: "天", 1: "个"}[prop.flow]
        return linecard(
            (
                f"[font][][60][color][{prop.color}]【{prop.name}】[nowrap][passport]\n"
                f"[right]{format_number(n)}{quant}\n"
                f"----\n{prop.intro.replace('\n','[passport]\n')}"
                f"\n[right]{prop.tip.replace('\n','[passport]\n')}"
            ),
            font_manager,
            40,
            width=880,
            autowrap=True,
        )

    return [result(*args) for args in data]


def prop_card(data: list[tuple[Prop, int]], tip: str = None):
    data.sort(key=lambda x: x[0].rare)

    def result(prop: Prop, n: int):
        quant = {0: "天", 1: "个"}.get(prop.flow)
        return (
            f"[color][{prop.color}]{prop.name}[nowrap][passport]\n"
            f"[pixel][350]{prop.rare*'☆'}[nowrap][passport]\n"
            f"[right]{format_number(n)}{quant}"
        )

    info = "\n".join(result(*args) for args in data)
    if tip:
        info += "\n" + endline(tip)
    return linecard(info, font_manager, 40, spacing=1.5, width=880)


def invest_card(data: list[tuple[Stock, int]], tip: str = None):
    def result(stock: Stock, n: int):
        return (
            f"[pixel][20]公司 {stock.name}\n"
            f"[pixel][20]结算 [nowrap]\n[color][green]{format_number(stock.floating / stock.issuance)}[nowrap]\n"
            f"[pixel][400]数量 [nowrap]\n[color][green]{n}"
        )

    info = "\n".join(result(*args) for args in data)
    if tip:
        info += "\n" + endline(tip)
    return linecard(info, font_manager, 40, width=880)


def draw_rank(data: list[tuple[str, int, bytes]]) -> IMG:
    """
    排名信息
    """
    first = data[0][1]
    canvas = Image.new("RGBA", (880, 80 * len(data) + 20))
    draw = ImageDraw.Draw(canvas)
    y = 20
    i = 1
    font = font_manager.font(40)
    circle_mask = Image.new("RGBA", (60, 60), (255, 255, 255, 0))
    ImageDraw.Draw(circle_mask).ellipse(((0, 0), (60, 60)), fill="black")
    for nickname, v, avatar in data:
        if avatar:
            avatar = Image.open(BytesIO(avatar)).resize((60, 60))
            canvas.paste(avatar, (5, y), circle_mask)
        draw.rectangle(((70, y + 10), (70 + int(v / first * 790), y + 50)), fill="#99CCFFCC")
        draw.text((80, y + 10), f"{i+1}.{nickname} {format_number(v)}", fill=(0, 0, 0), font=font)
        y += 80
        i += 1
    return canvas
