import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
from clovers_leafgame.output import text_to_image, endline


def account_card(
    dist: list[tuple[int, str]],
    info: str,
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
    canvas = Image.new("RGBA", (880, 400))
    dist.sort(key=lambda x: x[0], reverse=True)
    labels = []
    x = []
    sum_gold = 0
    for N, (gold, group_name) in enumerate(dist):
        if N < 8 and gold > 0.01 * sum_gold:
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
    plt.legend(labels, loc=(-0.6, 0), frameon=False)
    plt.axis("equal")
    plt.subplots_adjust(top=0.95, bottom=0.05, left=0.32, hspace=0, wspace=0)
    plt.savefig(output, format="png", dpi=100, transparent=True)
    plt.close()

    statistics = Image.open(output)
    canvas.paste(statistics, (880 - statistics.size[0], 0))
    text_to_image(info + endline("账户信息"), height=400, canvas=canvas)
    return canvas
