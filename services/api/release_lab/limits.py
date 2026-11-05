"""Bounded per-process login throttle; deployment-wide limits belong at the ingress."""

from collections import OrderedDict, deque
import threading
import time
from fastapi import HTTPException

_attempts = OrderedDict()
_lock = threading.Lock()


def login_limit(address, username):
    current = time.monotonic()
    key = (address, username)
    with _lock:
        recent = _attempts.setdefault(key, deque())
        while recent and current - recent[0] >= 60:
            recent.popleft()
        _attempts.move_to_end(key)
        if len(recent) >= 30:
            raise HTTPException(
                429, "Too many sign-in attempts; try again in one minute", headers={"Retry-After": "60"}
            )
        recent.append(current)
        while len(_attempts) > 1024:
            _attempts.popitem(last=False)
