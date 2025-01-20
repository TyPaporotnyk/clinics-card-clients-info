import logging
import time

from gspread.exceptions import APIError

logger = logging.getLogger(__name__)


def retry_request(retries=5, delay=10):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except APIError as e:
                    if e.response.status_code in [500, 503]:
                        logger.warning("Retrying... (%s / %s) wait for %s secconds", attempt + 1, retries, delay)
                        time.sleep(delay)
                    else:
                        raise
            raise Exception("Max retries exceeded")

        return wrapper

    return decorator
