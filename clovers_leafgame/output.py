from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG
from io import BytesIO

from .core.data import Bank, Item, Prop, Stock
from .utils.linecard import FontManager, linecard
from .utils.tools import format_number
from .config import config

font_manager = FontManager(
    config.fontname,
    config.fallback_fonts,
    (30, 40, 60),
)


def end_line(tip: str) -> str:
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


def prop_card(data: list[tuple[Prop, int]], endline: str = "仓库列表"):
    data.sort(key=lambda x: x[0].rare)

    def result(prop: Prop, n: int):
        quant = {0: "天", 1: "个"}.get(prop.flow)
        return (
            f"[color][{prop.color}]{prop.name}[nowrap][passport]\n"
            f"[pixel][350]{prop.rare*'☆'}[nowrap][passport]\n"
            f"[right]{format_number(n)}{quant}"
        )

    return linecard(
        "\n".join(result(*args) for args in data) + "\n" + end_line(endline),
        font_manager,
        40,
        spacing=1.5,
        width=880,
    )


def invest_card(data: list[tuple[Stock, int]]):
    info = []
    for stock, n in data:
        stock_value = format_number(stock.floating / stock.issuance)
        info.append(
            f"[pixel][20]公司 {stock.name}\n"
            f"[pixel][20]结算 [nowrap]\n[color][green]{stock_value}[nowrap]\n"
            f"[pixel][400]数量 [nowrap]\n[color][green]{n}"
        )
    info.append(end_line("投资列表"))
    return linecard("\n".join(info), font_manager, 40, width=880)


import numpy as np

curve_fit = {
    1: lambda x: 0.339438628551138 * np.log(2.7606559801569316e-13 * x) + -0.0012286453324789554 * x + 9.310675305999386,
    2: lambda x: 0.2622830460672209 * np.log(1.0565997436401555e-10 * x) + -0.0013800074822243364 * x + 6.079586419253099,
    3: lambda x: 0.16563555661021917 * np.log(652.209392293454 * x) + -0.0009688421476907207 * x + -0.5084815403474984,
    4: lambda x: -0.11977280212351049 * np.log(3.53822027614143e-11 * x) + 0.0005645672140693966 * x + -0.9186502372819698,
    5: lambda x: -0.27071466714377795 * np.log(1.2743174700041504e-11 * x) + 0.0014031052967047675 * x + -4.106094299018067,
    6: lambda x: -0.5213387432196357 * np.log(16.300736342820436 * x) + 0.0027842719423569447 * x + 5.3464181044586425,
}


def gacha_report_card(
    nickname: str,
    prop_star: int,
    prop_n: int,
    air_star: int,
    air_n: int,
):
    N = prop_n + air_n
    pt = prop_star / N
    title = []
    if not prop_n:
        title.append("[center][color][#003300]理 想 气 体")
    elif pt < curve_fit[1](N):
        title.append("[center][color][#003300]很多空气")
    elif pt < curve_fit[2](N):
        title.append("[left][color][#003333]☆[nowrap][passport]\n[center]数据异常[nowrap][passport]\n[right]☆")
    elif pt < curve_fit[3](N):
        title.append("[left][color][#003366]☆ ☆[nowrap][passport]\n[center]一枚硬币[nowrap][passport]\n[right]☆ ☆")
    elif pt < curve_fit[4](N):
        title.append("[left][color][#003399]☆ ☆ ☆[nowrap][passport]\n[center]高斯分布[nowrap][passport]\n[right]☆ ☆ ☆")
    elif pt < curve_fit[5](N):
        title.append("[left][color][#0033CC]☆ ☆ ☆ ☆[nowrap][passport]\n[center]对称破缺[nowrap][passport]\n[right]☆ ☆ ☆ ☆")
    elif pt < curve_fit[6](N):
        title.append("[left][color][#0033FF]☆ ☆ ☆ ☆ ☆[nowrap][passport]\n[center]概率之子[nowrap][passport]\n[right]☆ ☆ ☆ ☆ ☆")
    else:
        title.append("[center][color][#FF0000]☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆☆")
    title.append(
        "----\n"
        f"抽卡次数 {N}[nowrap]\n"
        f"[pixel][450]空气占比 {round(air_n*100/N,2)}%\n"
        f"获得☆ {prop_star}[nowrap]\n"
        f"[pixel][450]获得☆ {air_star}\n"
        f"道具平均☆ {round(prop_star/(prop_n or 1),3)}[nowrap]\n"
        f"[pixel][450]空气平均☆ {round(air_star/(air_n or 1),3)}\n"
        f"数据来源：{nickname}"
    )
    title.append(end_line("抽卡报告"))
    return linecard("\n".join(title), font_manager, 40, width=880)


def bar_chart(info: str, lenth: float):
    """
    带头像的条形图
    """
    canvas = Image.new("RGBA", (880, 60))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(((70, 10), (860, 50)), fill="#00000033")
    draw.rectangle(((70, 10), (80 + int(lenth * 780), 50)), fill="#99CCFF")
    draw.text((80, 10), info, fill=(0, 0, 0), font=font_normal)

    async def func(url: str):
        avatar = Image.open(await download_url(url))
        avatar = avatar.resize((60, 60))
        circle_mask = Image.new("RGBA", avatar.size, (255, 255, 255, 0))
        ImageDraw.Draw(circle_mask).ellipse(((0, 0), avatar.size), fill="black")
        canvas.paste(avatar, (5, 0), circle_mask)
        return canvas

    return func


def draw_rank(data: list[tuple[str, BytesIO, int]]) -> IMG:
    """
    排名信息
    """
    first = data[0][1]
    canvas = Image.new("RGBA", (880, 100 * len(data) + 20))
    draw = ImageDraw.Draw(canvas)
    y = 20
    i = 1
    for nickname, v, avatar in data:
        draw.rectangle(((70, y + 30), (70 + int(v / first * 790), y + 70)), fill="#99CCFF")
        draw.text((80, y + 30), f"{i+1}.{nickname}：{format_number(v)}", fill=(0, 0, 0), font=font_manager.font(40))
        avatar = Image.open(avatar).resize((60, 60))
        circle_mask = Image.new("RGBA", avatar.size, (255, 255, 255, 0))
        ImageDraw.Draw(circle_mask).ellipse(((0, 0), avatar.size), fill="black")
        canvas.paste(avatar, (5, y + 20), circle_mask)
        y += 100
        i += 1
    return canvas
    # info.append(await bar_chart(f"{i+1}.{nicname(user)}：{format_ranktitle(x,title)}\n", x / first)(user.avatar_url))
