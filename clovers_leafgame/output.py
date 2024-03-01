import numpy as np
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

from clovers_leafgame_core.data import Prop, Stock
from clovers_utils.linecard import FontManager, linecard
from clovers_utils.tools import format_number
from .main import config

main_path = config.main_path

font_manager = FontManager(
    config.fontname,
    config.fallback_fonts,
    (30, 40, 60),
)

plt.rcParams["font.family"] = font_manager.font_name
plt.rcParams["font.sans-serif"] = font_manager.fallback


def endline(tip: str) -> str:
    return f"----\n[right][color][grey][font][][30]{tip}"


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
        issuance = stock.issuance
        unit = format_number(stock.floating / issuance) if issuance else "未发行"
        return (
            f"[pixel][20]{stock.name}\n"
            f"[pixel][20]结算 [nowrap]\n[color][green]{unit}[nowrap]\n"
            f"[pixel][400]数量 [nowrap]\n[color][green]{n}"
        )

    info = "\n".join(result(*args) for args in data)
    if tip:
        info += "\n" + endline(tip)
    return linecard(info, font_manager, 40, width=880)


AVATAR_MASK = Image.new("RGBA", (260, 260), (255, 255, 255, 0))
ImageDraw.Draw(AVATAR_MASK).ellipse(((0, 0), (260, 260)), fill="black")


def avatar_card(avatar: bytes, nickname: str, lines: list[tuple[str, str]]):
    font = font_manager.font(40)
    canvas = Image.new("RGBA", (880, 300))
    avatar = Image.open(BytesIO(avatar)).resize((260, 260))
    canvas.paste(avatar, (20, 20), AVATAR_MASK)
    draw = ImageDraw.Draw(canvas)
    draw.text((300, 40), f"{nickname}", fill=(0, 0, 0), font=font)
    draw.line(((300, 120), (860, 120)), fill="gray", width=4)
    for n, line in enumerate(lines):
        draw.text((300, 140 + n * 50), "•", fill="gray", font=font)
        draw.text((840, 140 + n * 50), "•", fill="gray", font=font)
        x = 340
        for char in line:
            draw.text((x, 140 + n * 50), char, fill="gray", font=font)
            x += 40

    return canvas


def account_card(dist: list[tuple[int, str]], info: str, colors=["#6699CC", "#66CCFF", "#669999", "#66CCCC", "#669966", "#66CC99"]):
    canvas = Image.new("RGBA", (880, 400))
    dist.sort(key=lambda x: x[0], reverse=True)
    labels = []
    x = []
    sum_gold = 0
    for N, (gold, group_name) in enumerate(dist):
        if N < 5 and gold > 0.01 * sum_gold:
            x.append(gold)
            labels.append(group_name)
            sum_gold += gold
        else:
            labels.append("其他")
            x.append(sum(seg[0] for seg in dist[N:]))
            break
    N += 1
    output = BytesIO()

    plt.figure(figsize=(6.6, 3.4))
    plt.pie(
        np.array(x),
        labels=labels[0:N],
        autopct="%1.1f%%",
        colors=colors[0:N],
        wedgeprops={"width": 0.38, "edgecolor": "none"},
        textprops={"fontsize": 20},
        pctdistance=0.81,
        labeldistance=1.05,
    )
    plt.axis("equal")
    plt.subplots_adjust(top=0.95, bottom=0.05, left=0.32, hspace=0, wspace=0)
    plt.savefig(output, format="png", dpi=100, transparent=True)
    plt.close()

    statistics = Image.open(output)
    canvas.paste(statistics, (880 - statistics.size[0], 0))
    linecard(info + "\n" + endline("账户信息"), font_manager, 40, width=880, height=400, canvas=canvas)
    return canvas
