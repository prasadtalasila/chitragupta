# Import only time + runlock: spawn re-imports this module on the parent's
# sys.path, where cv2/typing shadows stdlib typing and the child dies before
# taking the lock (#45).
import time

from chitragupta import runlock

HELD_FOR = 120


# Ended by kill, not a second Event: a process killed inside Event.wait()
# dies holding its semaphore, and the parent's set() then blocks forever.
def hold(path, started):
    with runlock.pipeline_lock(path):
        started.set()
        time.sleep(HELD_FOR)
