import numpy as np
from clovers_leafgame.output import text_to_image, endline

curve_fit = {
    1: lambda x: 0.339438628551138 * np.log(2.7606559801569316e-13 * x) + -0.0012286453324789554 * x + 9.310675305999386,
    2: lambda x: 0.2622830460672209 * np.log(1.0565997436401555e-10 * x) + -0.0013800074822243364 * x + 6.079586419253099,
    3: lambda x: 0.16563555661021917 * np.log(652.209392293454 * x) + -0.0009688421476907207 * x + -0.5084815403474984,
    4: lambda x: -0.11977280212351049 * np.log(3.53822027614143e-11 * x) + 0.0005645672140693966 * x + -0.9186502372819698,
    5: lambda x: -0.27071466714377795 * np.log(1.2743174700041504e-11 * x) + 0.0014031052967047675 * x + -4.106094299018067,
    6: lambda x: -0.5213387432196357 * np.log(16.300736342820436 * x) + 0.0027842719423569447 * x + 5.3464181044586425,
}


def report_card(
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
    return text_to_image("\n".join(title) + endline("抽卡报告"))
