import re

prop_name = "金币"
command = "使用道具 金币2"

res = re.match(f"使用(道具)?\\s*{prop_name}\\s*(\\d*)(.*)", command)
res = re.match(f"使用道具?\\s*{prop_name}", command)
if res:
    print(res.groups())
