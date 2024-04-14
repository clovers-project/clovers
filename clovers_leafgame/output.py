import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO
from PIL import Image, ImageDraw
from .core.data import Prop, Stock
from clovers.utils.linecard import FontManager, linecard
from clovers.utils.tools import format_number
from .main import config_data

fontname = config_data.fontname
fallback = config_data.fallback_fonts

font_manager = FontManager(fontname, fallback, (30, 40, 60))

plt.rcParams["font.family"] = fontname
plt.rcParams["font.sans-serif"] = fallback


def text_to_image(text: str, font_size=40, width=880, **kwargs):
    return linecard(text, font_manager, font_size, width, **kwargs)


def endline(tip: str) -> str:
    return f"\n----\n[right][color][grey][font][][30]{tip}"


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


def prop_card(data: list[tuple[Prop, int]], tip: str | None = None):
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
        info += endline(tip)
    return linecard(info, font_manager, 40, spacing=1.5, width=880)


def invest_card(data: list[tuple[Stock, int]], tip: str | None = None):
    def result(stock: Stock, n: int):
        issuance = stock.issuance
        buy = format_number(max(stock.floating, stock.value) / issuance) if issuance else "未发行"
        sell = format_number(stock.floating / issuance) if issuance else "未发行"
        return (
            f"[pixel][20]{stock.name}\n"
            f"[pixel][20]数量 [nowrap]\n[color][{'green' if n else 'red'}]{n}[nowrap]\n"
            f"[pixel][280]购买 [nowrap]\n[color][{'red' if buy > sell else 'green'}]{buy}[nowrap]\n"
            f"[pixel][580]结算 [nowrap]\n[color][green]{sell}[nowrap]\n"
        )

    info = "\n".join(result(*args) for args in data)
    if tip:
        info += endline(tip)
    return linecard(info, font_manager, 40, width=880)


AVATAR_MASK = Image.new("RGBA", (260, 260), (255, 255, 255, 0))
ImageDraw.Draw(AVATAR_MASK).ellipse(((0, 0), (260, 260)), fill="black")


def avatar_card(avatar: bytes | None, nickname: str, lines: list[str]):
    font = font_manager.font(40)
    canvas = Image.new("RGBA", (880, 300))
    if avatar:
        canvas.paste(Image.open(BytesIO(avatar)).resize((260, 260)), (20, 20), AVATAR_MASK)
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


def candlestick(figsize: tuple[float, float], length: int, history: list[tuple[float, float]]):
    """
    生成股价K线图
        figsize:图片尺寸
        length:OHLC采样长度
        history:历史数据
    """
    t, price = zip(*history)
    l = len(t)
    t = [t[i : i + length] for i in range(0, l, length)]
    price = [price[i : i + length] for i in range(0, l, length)]
    D, O, H, L, C = [], [], [], [], []
    for i in range(len(price)):
        D.append(datetime.fromtimestamp(t[i][0]))
        O.append(price[i][0])
        H.append(max(price[i]))
        L.append(min(price[i]))
        C.append(price[i][-1])
    data = pd.DataFrame({"date": D, "open": O, "high": H, "low": L, "close": C})
    data = data.set_index("date")
    style = mpf.make_mpf_style(
        base_mpf_style="charles",
        marketcolors=mpf.make_marketcolors(up="#006340", down="#a02128", edge="none"),
        y_on_right=False,
        facecolor="#FFFFFF99",
        figcolor="none",
    )
    output = BytesIO()
    mpf.plot(
        data,
        type="candlestick",
        xlabel="",
        ylabel="",
        datetime_format="%H:%M",
        tight_layout=True,
        style=style,
        figsize=figsize,
        savefig=output,
    )
    return Image.open(output)


def dist_card(
    dist: list[tuple[int, str]],
    colors=[
        "#351c75",
        "#0b5394",
        "#1155cc",
        "#134f5c",
        "#38761d",
        "#bf9000",
        "#b45f06",
        "#990000",
        "#741b47",
    ],
):
    dist.sort(key=lambda x: x[0], reverse=True)
    labels = []
    x = []
    sum_value = sum(d[0] for d in dist)
    limit = 0.01 * sum_value
    for n, (value, name) in enumerate(dist):
        if n < 8 and value > limit:
            x.append(value)
            labels.append(name)
        else:
            labels.append("其他")
            x.append(sum(seg[0] for seg in dist[n:]))
            break
    n += 1
    output = BytesIO()

    plt.figure(figsize=(6.6, 3.4))
    plt.pie(
        np.array(x),
        labels=[""] * n,
        autopct=lambda pct: "" if pct < 1 else f"{pct:.1f}%",
        colors=colors[0:n],
        wedgeprops={"edgecolor": "none"},
        textprops={"fontsize": 15},
        pctdistance=1.2,
        explode=[0, 0.1, 0.19, 0.27, 0.34, 0.40, 0.45, 0.49, 0.52][0:n],
    )
    plt.legend(labels, loc=(-0.6, 0), frameon=False)
    plt.axis("equal")
    plt.subplots_adjust(top=0.95, bottom=0.05, left=0.4, hspace=0, wspace=0)
    plt.savefig(output, format="png", dpi=100, transparent=True)
    plt.close()
    canvas = Image.new("RGBA", (880, 340))
    canvas.paste(Image.open(output), (220, 0))
    return canvas
