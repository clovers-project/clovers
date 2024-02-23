from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG
from io import BytesIO


from .core.data import Bank, Prop, Stock
from .core.linecard import FontManager, linecard, info_splicing
from .core.utils import format_number
from .main import config, manager

main_path = config.main_path

font_manager = FontManager(
    config.fontname,
    config.fallback_fonts,
    (30, 40, 60),
)


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
