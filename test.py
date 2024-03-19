import timeit


def main():
    dist: list[tuple[int, str]] = []


execution_time = timeit.timeit(main, number=1000000)
print("func_1:", execution_time, "seconds")
