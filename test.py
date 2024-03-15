import re

text = "金币查询a"
print(re.match(r"查询$", text))
print(re.match(r"查询", text))
print(re.match(r".+查询$", text))
print(re.match(r".+查询", text))
