import time
from functools import reduce
from operator import or_

set_list = [{1, 2, 3}, {2, 3, 4}, {3, 4, 5}, {4, 5, 6}]  # 很长的set列表

looptimes = 1000000
start = time.time()
for i in range(looptimes):
    union_set = set()
    for subset in set_list:
        union_set.update(subset)

print(time.time() - start)

start = time.time()

for i in range(looptimes):
    union_set = set().union(*set_list)

print(time.time() - start)

start = time.time()
for i in range(looptimes):
    union_set = reduce(or_, set_list)

print(time.time() - start)
