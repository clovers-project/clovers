import sys
import traceback


def xferout_check(xfer: int):
    """是否能转入"""
    limit = 20000
    record = -15000
    if limit <= record:
        return None
    if limit < record + xfer:
        return limit - record
    return xfer


print(xferout_check(100000))
