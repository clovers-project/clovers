import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from PIL import Image
from clovers_leafgame.output import text_to_image, endline


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
    text_to_image(info + endline("账户信息"), height=400, canvas=canvas)
    return canvas


async def group_info(stock: Stock, avatar_url: str, members_n: int, record: list[tuple[float, float]]):
    """
    群资料卡
        nickname: 名称
        avatar_url: 头像路径
        members_n: 成员数
        record: 股票价格记录, seg: 时间，价格
    """
    info = []
    # 加载群信息
    group = manager.data.group(group_id)
    info = []
    lines = [
        f"注册成员 {members_n}",
        f"发行时间 {datetime.fromtimestamp(t).strftime('%Y 年 %m 月 %d 日')if (t :=group.stock.time) else '未发行'}",
    ]
    info.append(avatar_card(await download_url(group.avatar_url), nickname, lines))
    if record:
        info.append(candlestick((9.5, 3), 12, record))

    if data := props_data(group.bank):
        info.append(prop_card(data, "群金库"))
    if data := invest_data(group.invest):
        info.append(invest_card(data, "群投资"))
    # 加载公司信息
    if company_name:
        # 注册信息
        msg = f"公司等级 {company.level}\n" f"成立时间 {datetime.datetime.fromtimestamp(company.time).strftime('%Y 年 %m 月 %d 日')}\n"
        info.append(linecard(msg + stock_profile(company), width=880, endline="注册信息"))
        # 蜡烛图
        ohlc = await Manager.candlestick(group_id)
        if ohlc:
            info.append(ohlc)
        # 资产分布
        invist = Counter(company.invest)
        for inner_user_id in group.namelist:
            invist += Counter(Manager.locate_user_at(inner_user_id, group_id)[1].invest)
        dist = []
        for inner_company_id, n in invist.items():
            inner_company = Manager.locate_group(inner_company_id).company
            inner_company_name = inner_company.company_name or f"（{str(inner_company_id)[-4:]}）"
            unit = max(inner_company.float_gold / inner_company.issuance, 0)
            dist.append([unit * n, inner_company_name])

        if dist:
            info.append(group_info_account(company, dist))

        ranklist = [(inner_user_id, exchange) for inner_user_id, exchange in company.exchange.items() if exchange.n > 0]
        if ranklist:
            ranklist.sort(key=lambda x: x[1].quote)

            def result(inner_user_id, exchange):
                nickname = Manager.get_user(inner_user_id).nickname
                nickname = nickname if len(nickname) < 7 else nickname[:6] + ".."
                return f"[pixel][20]{nickname}[nowrap]\n[pixel][300]单价 {exchange.quote}[nowrap]\n[pixel][600]数量 {exchange.n}\n"

            msg = "".join(result(inner_user_id, exchange) for inner_user_id, exchange in ranklist[:10])
            info.append(linecard(msg, width=880, font_size=40, endline="市场详情"))

        msg = company.intro
        if msg:
            info.append(linecard(msg + "\n", width=880, font_size=40, endline="公司介绍"))

    # 路灯挂件
    ranklist = list(group.Achieve_revolution.items())
    if ranklist:
        ranklist.sort(key=lambda x: x[1], reverse=True)

        def result(inner_user_id, n):
            user, group_account = Manager.locate_user_at(inner_user_id, group_id)
            return f"{group_account.nickname or user.nickname}[nowrap]\n[right]{n}次\n"

        msg = "".join(result(inner_user_id, n) for inner_user_id, n in ranklist[:10])
        info.insert(min(len(info), 2), linecard(msg, width=880, endline="路灯挂件"))

    return info_splicing(info, Manager.BG_path(bg_id), 10)
