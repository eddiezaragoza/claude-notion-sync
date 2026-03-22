import time
import logging

logger = logging.getLogger("notion_sync")


class RateLimiter:
    def __init__(self, min_interval=0.4, max_retries=5):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.last_request_time = 0.0
        self.request_count = 0

    def wait(self):
        now = time.monotonic()
        elapsed = now - self.last_request_time
        if self.last_request_time > 0 and elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.monotonic()
        self.request_count += 1

    def call_with_retry(self, fn, *args, **kwargs):
        self.wait()
        for attempt in range(self.max_retries):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                # Check for Notion API 429 rate limit
                is_rate_limit = False
                try:
                    from notion_client.errors import APIResponseError
                    if isinstance(e, APIResponseError) and e.status == 429:
                        is_rate_limit = True
                except ImportError:
                    pass

                if is_rate_limit:
                    backoff = min(2 ** attempt, 30)
                    logger.warning(f"Rate limited, backing off {backoff}s (attempt {attempt + 1})")
                    time.sleep(backoff)
                    self.last_request_time = time.monotonic()
                    self.request_count += 1
                else:
                    raise
        raise Exception(f"Rate limit exceeded after {self.max_retries} retries")
