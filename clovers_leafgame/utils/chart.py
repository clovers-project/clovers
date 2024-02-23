from typing import Tuple, List
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont
from PIL.Image import Image as IMG
from fontTools.ttLib import TTFont
from collections import Counter

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns
import numpy as np

import re
from re import Pattern

from ..core.utils import download_url


def alchemy_info(alchemy: dict, nickname: str, avatar: bytes):
    """
    炼金账户
    """
    canvas = Image.new("RGBA", (880, 400))
    avatar = Image.open(avatar).resize((160, 160))
    circle_mask = Image.new("RGBA", avatar.size, (255, 255, 255, 0))
    ImageDraw.Draw(circle_mask).ellipse(((0, 0), avatar.size), fill="black")
    canvas.paste(avatar, (20, 20), circle_mask)
    draw = ImageDraw.Draw(canvas)
    draw.line(((20, 200), (480, 200)), fill="gray", width=4)

    alchemy = Counter(alchemy)
    # 创建变量标签
    labels = ["蒸汽", "雷电", "岩浆", "尘埃", "沼泽", "寒冰"]
    # 创建变量值
    values = [
        alchemy["5"],
        alchemy["9"],
        alchemy["8"],
        alchemy["0"],
        alchemy["6"],
        alchemy["7"],
    ]
    products = max(values)
    # 计算角度
    angles = np.linspace(0.5 * np.pi, 2.5 * np.pi, 6, endpoint=False).tolist()
    angles = [(x if x < 2 * np.pi else x - 2 * np.pi) for x in angles]
    # 闭合雷达图
    values.append(values[0])
    angles.append(angles[0])
    # 绘制雷达图
    mainproduct = max(values)
    mainproduct = max(mainproduct, 1)
    values = [x * 4 / mainproduct for x in values]
    sns.set(font="simsun")
    plt.figure(figsize=(4, 4))
    ax = plt.subplot(111, polar=True)
    ax.plot(angles, values, linewidth=2, linestyle="solid")
    ax.fill(angles, values, "b", alpha=0.1)
    ax.set_yticklabels([])
    plt.xticks(angles[:-1], labels, fontsize=12)
    output = BytesIO()
    plt.savefig(output, transparent=True)
    canvas.paste(Image.open(output), (480, 0))

    water, fire, earth, wind = alchemy["1"], alchemy["2"], alchemy["3"], alchemy["4"]
    elements = [water, fire, earth, wind]
    max_value = max(elements)
    ethereum = max(min([water, fire, earth, wind]) - 2, 0)
    tag = f'{"元素炼金师" if ethereum*4 > products else "传统炼金师"} Lv.{integer_log(ethereum,2)}'
    draw.text((20, 240), tag, fill=(0, 0, 0), font=font_big)
    draw.text((21, 241), tag, fill=(0, 0, 0), font=font_big)
    tag = f"主要元素 {'|'.join({0:'水',1:'火',2:'土',3:'风'}[i] for i, value in enumerate(elements) if value == max_value)}"
    draw.text((20, 320), tag, fill=(0, 0, 0), font=font_big)
    draw.text((21, 321), tag, fill=(0, 0, 0), font=font_big)
    draw.text((200, 70), nickname, fill=(0, 0, 0), font=font_big)
    info = [canvas]

    def bar_chart(info: str, lenth: float, color: str = "99CCFF"):
        """
        条形图
        """
        canvas = Image.new("RGBA", (880, 60))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(((20, 10), (860, 50)), fill="#00000033")
        draw.rectangle(((20, 10), (80 + int(lenth * 780), 50)), fill=color)
        draw.text((30, 10), info, fill=(0, 0, 0), font=font_normal)
        return canvas

    level = integer_log(water, 2)
    info.append(bar_chart(f"水元素Lv.{level}", water / 2 ** (level + 1), "#66CCFFCC"))
    level = integer_log(fire, 2)
    info.append(bar_chart(f"火元素Lv.{level}", fire / 2 ** (level + 1), "#CC3300CC"))
    level = integer_log(earth, 2)
    info.append(bar_chart(f"土元素Lv.{level}", earth / 2 ** (level + 1), "#996633CC"))
    level = integer_log(wind, 2)
    info.append(bar_chart(f"风元素Lv.{level}", wind / 2 ** (level + 1), "#99CCFFCC"))

    element = alchemy["5"]
    level = integer_log(element, 2)
    info.append(bar_chart(f"蒸汽Lv.{level}", element / 2 ** (level + 1), "#CCFFFFCC"))
    element = alchemy["6"]
    level = integer_log(element, 2)
    info.append(bar_chart(f"沼泽Lv.{level}", element / 2 ** (level + 1), "#666633CC"))
    element = alchemy["7"]
    level = integer_log(element, 2)
    info.append(bar_chart(f"寒冰Lv.{level}", element / 2 ** (level + 1), "#0099FFCC"))
    element = alchemy["8"]
    level = integer_log(element, 2)
    info.append(bar_chart(f"岩浆Lv.{level}", element / 2 ** (level + 1), "#990000CC"))
    element = alchemy["9"]
    level = integer_log(element, 2)
    info.append(bar_chart(f"雷电Lv.{level}", element / 2 ** (level + 1), "#9900FFCC"))
    element = alchemy["0"]
    level = integer_log(element, 2)
    info.append(bar_chart(f"尘埃Lv.{level}", element / 2 ** (level + 1), "#99CCCCCC"))
    return info


def my_info_head(gold: int, win: int, lose: int, nickname: str, avatar: bytes):
    """
    我的资料卡第一个信息
    """
    canvas = Image.new("RGBA", (880, 300))
    avatar = Image.open(avatar).resize((260, 260))
    circle_mask = Image.new("RGBA", (260, 260), (255, 255, 255, 0))
    print(id(circle_mask))
    ImageDraw.Draw(circle_mask).ellipse(((0, 0), avatar.size), fill="black")
    canvas.paste(avatar, (20, 20), circle_mask)
    draw = ImageDraw.Draw(canvas)
    draw.text((300, 40), f"{nickname}", fill=(0, 0, 0), font=font_big)
    draw.line(((300, 120), (860, 120)), fill="gray", width=4)
    draw.text((300, 140), f"金币 {'{:,}'.format(gold)}", fill=(0, 0, 0), font=font_normal)
    draw.text((300, 190), f"战绩 {win}:{lose}", fill=(0, 0, 0), font=font_normal)
    draw.text((300, 240), f"胜率 {(round(win * 100 / (win + lose), 2) if win > 0 else 0)}%\n", fill=(0, 0, 0), font=font_normal)
    return canvas


def my_exchange_head(gold: int, nickname: str, invest: dict, avatar: bytes):
    """
    我的交易信息第一个信息
    """
    canvas = Image.new("RGBA", (880, 250))
    avatar = Image.open(avatar).resize((210, 210))
    circle_mask = Image.new("RGBA", avatar.size, (255, 255, 255, 0))
    ImageDraw.Draw(circle_mask).ellipse(((0, 0), avatar.size), fill="black")
    canvas.paste(avatar, (20, 20), circle_mask)
    draw = ImageDraw.Draw(canvas)
    draw.text((250, 40), f"{nickname}", fill=(0, 0, 0), font=font_big)
    draw.line(((250, 120), (860, 120)), fill="gray", width=4)
    draw.text((250, 140), f"金币 {'{:,}'.format(gold)}", fill=(0, 0, 0), font=font_normal)
    draw.text((250, 190), f"股票 {len(invest)}", fill=(0, 0, 0), font=font_normal)
    return canvas


def my_info_account(msg: str, dist):
    """
    我的资料卡账户分析
    """
    canvas = Image.new("RGBA", (880, 400))

    dist.sort(key=lambda x: x[0], reverse=True)
    labels = []
    x = []
    for N, (gold, group_name) in enumerate(dist):
        if N < 5:
            x.append(gold)
            labels.append(group_name)
        else:
            labels.append("其他")
            x.append(sum(seg[0] for seg in dist[N:]))
            break
    N += 1
    colors = ["#6699CC", "#66CCFF", "#669999", "#66CCCC", "#669966", "#66CC99"]
    output = BytesIO()

    plt.figure(figsize=(6.6, 3.4))
    plt.pie(
        np.array(x),
        labels=labels,
        autopct=lambda pct: "" if pct < 1 else f"{pct:.1f}%",
        colors=colors[0:N],
        wedgeprops={
            "width": 0.38,
            "edgecolor": "none",
        },
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
    linecard(msg, width=880, height=400, padding=(20, 30), endline="账户信息", canvas=canvas)
    return canvas


def group_info_head(company_name: str, group_id: int, member_count: int):
    """
    群资料卡第一个信息
    """
    canvas = Image.new("RGBA", (880, 250))
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (20, 40),
        company_name if company_name else "未注册",
        fill=(0, 0, 0),
        font=font_big,
    )
    draw.line(((0, 120), (880, 120)), fill="gray", width=4)
    draw.text((20, 140), f"注册：{str(group_id)[:4]}...", fill=(0, 0, 0), font=font_normal)
    draw.text((20, 190), f"成员：{member_count}", fill=(0, 0, 0), font=font_normal)
    return canvas


def group_info_account(company: Company, dist):
    """
    群资料卡账户分析
    """
    canvas = Image.new("RGBA", (880, 320))
    plt.figure(figsize=(8.8, 3.2))
    explode = [0, 0.1, 0.19, 0.27, 0.34, 0.40, 0.45, 0.49, 0.52]
    # 投资占比
    plt.subplot(1, 2, 1)
    plt.title("投资占比")
    plt.pie(
        [company.group_gold, int(sum(x[0] for x in dist))],
        labels=["", ""],
        autopct="%1.1f%%",
        colors=["#FFCC33", "#0066CC"],
        wedgeprops={
            "edgecolor": "none",
        },
        textprops={"fontsize": 15},
        pctdistance=1.2,
        explode=explode[0:2],
    )
    plt.legend(["金币", "股票"], loc=(-0.2, 0), frameon=False)
    # 资产分布
    plt.subplot(1, 2, 2)
    plt.title("资产分布")
    dist.sort(key=lambda x: x[0], reverse=True)
    labels = []
    x = []
    for N, (gold, group_name) in enumerate(dist):
        if N < 8:
            x.append(gold)
            labels.append(group_name)
        else:
            labels.append("其他")
            x.append(sum(seg[0] for seg in dist[N:]))
            break
    N += 1
    colors = [
        "#351c75",
        "#0b5394",
        "#1155cc",
        "#134f5c",
        "#38761d",
        "#bf9000",
        "#b45f06",
        "#990000",
        "#741b47",
    ]
    output = BytesIO()
    plt.pie(
        x,
        labels=[""] * N,
        autopct=lambda pct: "" if pct < 1 else f"{pct:.1f}%",
        colors=colors[0:N],
        wedgeprops={
            "edgecolor": "none",
        },
        textprops={"fontsize": 15},
        pctdistance=1.2,
        explode=explode[0:N],
    )
    plt.legend(labels, loc=(-0.6, 0), frameon=False)
    plt.subplots_adjust(top=0.9, bottom=0.1, left=0.05, right=0.95, hspace=0, wspace=0.6)
    plt.savefig(output, format="png", dpi=100, transparent=True)
    plt.close()

    return Image.open(output)


def gini_coef(wealths: list) -> float:
    """
    计算基尼系数
    """
    wealths.insert(0, 0)
    wealths_cum = np.cumsum(wealths)
    wealths_sum = wealths_cum[-1]
    N = len(wealths_cum)
    S = np.trapz(wealths_cum / wealths_sum, np.array(range(N)) / (N - 1))
    return 1 - 2 * S


def integer_log(number, base) -> int:
    result = 0
    while number >= base:
        number /= base
        result += 1
    return result
