import asyncio
import numpy as np
import httpx


async def download_url(url: str) -> bytes | None:
    async with httpx.AsyncClient() as client:
        for _ in range(3):
            try:
                resp = await client.get(url, timeout=20)
                resp.raise_for_status()
                return resp.content
            except httpx.HTTPStatusError:
                await asyncio.sleep(3)
            except:
                return None
    return None


def to_int(N) -> int | None:
    try:
        result = int(N)
    except ValueError:
        result = {
            "零": 0,
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }.get(N)
    return result


def format_number(num) -> str:
    if num < 10000:
        return "{:,}".format(round(num, 2))
    x = str(int(num))
    if 10000 <= num < 100000000:
        y = int(x[-4:])
        if y:
            return f"{x[:-4]}万{y}"
        return f"{x[:-4]}万"
    if 100000000 <= num < 1000000000000:
        y = int(x[-8:-4])
        if y:
            return f"{x[:-8]}亿{y}万"
        return f"{x[:-8]}亿"
    return "{:.2e}".format(num)


def gini_coef(wealths: list[int]) -> float:
    """
    计算基尼系数
    """
    wealths.sort()
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
