import time

def start():
    return time.time()

def stop(start_time):
    elapsed = time.time() - start_time
    ms = int((elapsed - int(elapsed)) * 1000)
    s = int(elapsed) % 60
    m = (int(elapsed) // 60) % 60
    h = int(elapsed) // 3600
    timer_str = f"{h:02d}:{m:02d}:{s:02d}:{ms:03d}"
    return timer_str