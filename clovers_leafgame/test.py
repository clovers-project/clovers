import asyncio
import timeit
import re


"金币排行机器人bug研究中心"
title = re.search(r"(.+)排行(.*)", "金币排行")
print(type(title.group(2)))
