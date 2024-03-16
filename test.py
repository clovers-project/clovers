import matplotlib.pyplot as plt
from datetime import datetime
import pandas as pd
from io import BytesIO
import mplfinance as mpf
import time
import random
from PIL import Image


def candlestick(figsize: tuple[float, float], length: int, history: list[tuple[float, float]]) -> BytesIO:
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
    return output


class Stock:
    issuance: int = 0
    """股票发行量"""
    time: float = None
    """注册时间"""
    floating: int = 0
    """浮动资产"""
    value: int = 0
    """全群资产"""
    exchange: dict[str, tuple[int, float]] = {}
    """交易信息"""
    fixed: int = 0
    gp: int = 0


class Group:
    id: str
    name: str = None
    avatar_url: str = None
    level: int = 1
    stock: Stock = Stock()
    invest: int = 0
    extra: dict = {}


def stock_update(group: Group):
    stock = group.stock
    # 更新全群金币数
    stock_value = stock.gp + stock.fixed
    # 股票价格变化：趋势性影响（正态分布），随机性影响（平均分布），向债务价值回归
    floating = stock.floating
    print(floating)
    floating += floating * random.gauss(0, 0.03)
    floating += stock_value * random.uniform(-0.1, 0.1)
    floating += (stock_value - floating) * 0.05
    # 已售出股票带来的浮动收入
    issuance = stock.issuance
    stock.fixed = int(stock.fixed * floating / stock.floating)
    stock.exchange = {user_id: exchange for user_id, exchange in stock.exchange.items() if exchange[0] > 0}
    # 更新浮动价格
    stock.floating = floating
    # 记录价格历史
    if not (stock_record := group.extra.get("stock_record")):
        stock_record = [(0.0, 0.0) for _ in range(720)]
    stock_record.append((time.time(), floating / issuance))
    stock_record = stock_record[-720:]
    group.extra["stock_record"] = stock_record


group = Group()
group.stock.value = 0
group.stock.floating = 200000
group.stock.issuance = 20000
group.invest = 0
group.stock.fixed = 100000
group.stock.gp = 100000
for i in range(360):
    stock_update(group)

# group.invest = 10000
# floating = group.stock.floating
# for i in range(10000):
#     unit = floating / 20000
#     group.stock.fixed -= unit
#     floating -= unit

for i in range(360):
    stock_update(group)

Image.open(candlestick((9.5, 3), 12, group.extra["stock_record"])).show()
