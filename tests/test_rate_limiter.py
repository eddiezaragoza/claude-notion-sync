import time
import pytest
from notion_sync.rate_limiter import RateLimiter


def test_rate_limiter_enforces_interval():
    limiter = RateLimiter(min_interval=0.1)
    start = time.monotonic()
    limiter.wait()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.1


def test_rate_limiter_no_wait_on_first_call():
    limiter = RateLimiter(min_interval=1.0)
    start = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - start
    assert elapsed < 0.05


def test_rate_limiter_tracks_request_count():
    limiter = RateLimiter(min_interval=0.01)
    assert limiter.request_count == 0
    limiter.wait()
    assert limiter.request_count == 1
    limiter.wait()
    assert limiter.request_count == 2


def test_call_with_retry_succeeds_on_first_try():
    limiter = RateLimiter(min_interval=0.01)
    result = limiter.call_with_retry(lambda: "success")
    assert result == "success"


def test_call_with_retry_succeeds_after_rate_limit():
    limiter = RateLimiter(min_interval=0.01, max_retries=3)
    call_count = 0
    def flaky_fn():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            # Simulate a 429 error similar to what notion-client raises
            import httpx
            from notion_client.errors import APIResponseError
            mock_response = httpx.Response(429, request=httpx.Request("POST", "https://api.notion.com/v1/test"))
            raise APIResponseError(mock_response, "Rate limited", "rate_limited")
        return "success"
    result = limiter.call_with_retry(flaky_fn)
    assert result == "success"
    assert call_count == 3


def test_call_with_retry_raises_non_rate_limit_errors():
    limiter = RateLimiter(min_interval=0.01)
    def bad_fn():
        raise ValueError("not a rate limit error")
    with pytest.raises(ValueError, match="not a rate limit error"):
        limiter.call_with_retry(bad_fn)
