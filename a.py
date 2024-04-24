import time

a = {k: str(k) for k in range(5)}

b = a

a = {}

a.update(b)

print(a)
