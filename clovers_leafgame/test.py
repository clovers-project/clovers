a = [1, 2, 3]
b = [4, 5, 6]

c = zip(a, b)

d = next(c)

print(d)

for x in c:
    print(x)
