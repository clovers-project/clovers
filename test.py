import random

event_list = [(10, 1), (20, 2), (40, 3), (60, 4), (100, 5)]
weights = []
events = []
before_randvalue = 0
for randvalue, event in event_list:
    weights.append(randvalue - before_randvalue)
    before_randvalue = randvalue
    events.append(event)

result = [0, 0, 0, 0, 0]

for i in range(10000):
    index = random.choices(events, weights, k=1)[0] - 1
    result[index] += 1

print(result)
