import time

from chitragupta import runlock

HELD_FOR = 120


def hold(path, started):
    with runlock.pipeline_lock(path):
        started.set()
        time.sleep(HELD_FOR)
