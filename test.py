import time

log = "加载"

for _ in range(50):
    print(log, end="")
    time.sleep(1)
    print("完成")
