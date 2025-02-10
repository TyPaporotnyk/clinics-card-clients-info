import logging
import threading
import time
from collections import deque
from functools import wraps

from gspread.exceptions import APIError

logger = logging.getLogger(__name__)


def retry_request(retries=5, delay=10):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    if e.response.status_code in [500, 503, 409]:
                        logger.warning("Retrying... (%s / %s) wait for %s secconds", attempt + 1, retries, delay)
                        time.sleep(delay)
                    else:
                        raise
            raise Exception("Max retries exceeded")

        return wrapper

    return decorator


def rate_limit(max_requests=60, per_seconds=60):
    lock = threading.Lock()
    requests_timestamps = deque(maxlen=max_requests)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                current_time = time.time()

                while requests_timestamps and current_time - requests_timestamps[0] >= per_seconds:
                    requests_timestamps.popleft()

                if len(requests_timestamps) >= max_requests:
                    sleep_time = requests_timestamps[0] + per_seconds - current_time
                    if sleep_time > 0:
                        time.sleep(sleep_time)

                requests_timestamps.append(time.time())

                return func(*args, **kwargs)

        return wrapper

    return decorator
